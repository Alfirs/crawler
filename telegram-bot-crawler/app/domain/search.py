from __future__ import annotations

from dataclasses import dataclass
from typing import List
import json
from pathlib import Path
from app.storage.db import Database
from app.config import AppConfig

@dataclass
class SearchResult:
    code: str
    description: str
    duty_pct: float
    confidence: float
    source: str # 'vector', 'fts', 'static'

class SearchService:
    def __init__(self, db: Database, config: AppConfig) -> None:
        self.db = db
        self.config = config
        
        # Initialize OpenAI client if key is present
        self.aclient = None
        if config.openrouter_api_key and config.openrouter_api_key != "STOPPED_EMERGENCY":
            try:
                from openai import AsyncOpenAI
                self.aclient = AsyncOpenAI(
                    api_key=config.openrouter_api_key,
                    base_url=config.openrouter_base_url,
                )
            except ImportError:
                print("OpenAI library not installed. LLM features disabled.")

    def ingest_data(self, json_path: str):
        """Loads TN VED data from JSON into the database."""
        path = Path(json_path)
        if not path.exists():
            print(f"File not found: {json_path}")
            return
            
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.db.execute_script("""
            CREATE TABLE IF NOT EXISTS tnved_codes (
                code TEXT PRIMARY KEY,
                description TEXT,
                duty_pct REAL,
                category TEXT
            );
        """)
        
        data_to_insert = []
        for item in data:
            data_to_insert.append((
                item["code"], 
                item["desc"], 
                item["duty"], 
                item.get("category", "other")
            ))
            
        self.db.executemany(
            "INSERT OR REPLACE INTO tnved_codes (code, description, duty_pct, category) VALUES (?, ?, ?, ?)",
            data_to_insert
        )
        print(f"Ingested {len(data_to_insert)} codes into DB.")

    async def search(self, query: str) -> List[SearchResult]:
        """
        Hybrid search:
        1. Exact match by Code (High confidence)
        2. SQL LIKE Search (Medium confidence)
        3. LLM (Disabled by default to save cost)
        """
        results = []
        placeholder = self.db.placeholder

        # 1. Direct Code Match
        clean_query = query.strip()
        row = self.db.fetchone(
            f"SELECT code, description, duty_pct FROM tnved_codes WHERE code = {placeholder}", 
            (clean_query,)
        )
        if row:
            results.append(SearchResult(
                code=row["code"],
                description=row["description"],
                duty_pct=row["duty_pct"],
                confidence=1.0,
                source="exact"
            ))
            return results

        # 2. Text Search (Smart Token Match)
        # Split query into tokens and filter
        import re
        tokens = [t.lower() for t in re.findall(r'\w+', clean_query) if len(t) > 2]
        
        # Get all candidates (table is small for MVP)
        rows = self.db.fetchall(f"SELECT code, description, duty_pct FROM tnved_codes")
        
        scored_results = []
        for row in rows:
            desc = row["description"].lower()
            # Simple scoring: how many tokens are present?
            # Basic stemming: "детские" -> "дет"
            match_count = 0
            for token in tokens:
                # Naive stem check
                root = token[:-2] if len(token) > 4 else token
                if root in desc:
                    match_count += 1
            
            if match_count > 0:
                # Calculate confidence based on coverage
                confidence = match_count / len(tokens) if tokens else 0
                if confidence > 0.4: # Tweak threshold
                    scored_results.append((confidence, row))
        
        # Sort by confidence
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        for score, row in scored_results[:5]:
            results.append(SearchResult(
                code=row["code"],
                description=row["description"],
                duty_pct=row["duty_pct"],
                confidence=score,
                source="fuzzy"
            ))

        
        # 3. LLM Search (If configured and local results are weak)
        # "Weak" = fewer than 3 results or top result < 0.8 confidence
        local_is_weak = len(results) < 3 or (results and results[0].confidence < 0.8)
        
        if self.aclient is not None and local_is_weak:
            try:
                print(f"[Search] Local results weak ({len(results)} items, top confidence: {results[0].confidence if results else 0}). Calling LLM...")
                llm_results = await self._ask_llm(query)
                
                if llm_results:
                    # If LLM returned good results, REPLACE weak local results
                    # (don't mix garbage local results with good LLM ones)
                    if llm_results[0].confidence >= 0.7:
                        print(f"[Search] LLM returned {len(llm_results)} results. Replacing weak local results.")
                        # Keep only high-confidence local results (exact matches)
                        good_local = [r for r in results if r.confidence >= 0.9]
                        results = good_local + llm_results
                    else:
                        # Merge normally if LLM also uncertain
                        existing_codes = {r.code for r in results}
                        for lr in llm_results:
                            if lr.code not in existing_codes:
                                results.append(lr)
            except Exception as e:
                print(f"LLM Search failed: {e}")

        # Final sort by confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    async def _ask_llm(self, query: str) -> List[SearchResult]:
        model = self.config.openrouter_model or "gpt-4o-mini"
        prompt = (
            f"Ты — эксперт по таможенному классификатору ТН ВЭД (HS Code) ЕАЭС.\n"
            f"Пользователь ищет товар: «{query}».\n\n"
            "Твоя задача: предложить 3 НАИБОЛЕЕ ПОДХОДЯЩИХ 10-значных кода ТН ВЭД для импорта в Россию.\n\n"
            "КРИТИЧЕСКИ ВАЖНО:\n"
            "1. Коды ДОЛЖНЫ соответствовать товару по смыслу!\n"
            "   - Одежда (брюки, юбки, платья) → группы 61-62\n"
            "   - Брюки мужские → 6203 (НЕ сумки, НЕ электроника!)\n"
            "   - Юбки женские → 6204\n"
            "   - Обувь → группа 64\n"
            "   - Игрушки → 9503\n"
            "2. ЗАПРЕЩЕНО предлагать коды из несвязанных категорий!\n"
            "3. Пошлина (duty) обычно 0-15%\n\n"
            "Ответ — строго JSON массив:\n"
            '[{"code": "6203423500", "description": "Брюки мужские из хлопка", "duty": 10.0, "confidence": 0.95}]\n\n'
            "ТОЛЬКО JSON, без лишнего текста!"
        )
        
        try:
            print(f"[LLM] Calling {model} for query: '{query}'")
            resp = await self.aclient.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            content = resp.choices[0].message.content
            print(f"[LLM] Raw response: {content[:500]}...")
            
            # Clean markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                 content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content)
            results = []
            for item in data:
                code = str(item.get("code", "")).strip().replace(" ", "")
                desc = item.get("description", "AI Suggestion")
                duty_raw = float(item.get("duty", 10.0))
                # Normalize: if > 1, it's percentage (e.g., 10.0 = 10%)
                duty_pct = duty_raw / 100.0 if duty_raw > 1.0 else duty_raw
                confidence = float(item.get("confidence", 0.8))
                
                print(f"[LLM] Parsed: {code} - {desc[:50]}... (duty={duty_pct*100:.1f}%, conf={confidence})")
                
                results.append(SearchResult(
                    code=code,
                    description=desc,
                    duty_pct=duty_pct,
                    confidence=confidence,
                    source="ai"
                ))
            return results
        except Exception as e:
            print(f"[LLM] Error: {e}")
            return []

    async def check_certification(self, product_name: str, tnved_code: str | None) -> str:
        """
        Ask LLM about certification requirements (TR TS, Declaration, etc).
        """
        if not self.aclient:
             return "⚠️ API ключ для AI не настроен. Проверка сертификации недоступна."

        model = self.config.openrouter_model or "gpt-4o-mini"
        code_str = f" (Код ТН ВЭД: {tnved_code})" if tnved_code else ""
        query = f"{product_name}{code_str}"
        
        # 1. Try Local DB (Official Lists)
        if tnved_code and len(tnved_code) >= 4:
            # Find rules where prefix matches the start of our code
            # e.g. Rule '6204' matches Code '620432...'
            rows = self.db.fetchall(
                "SELECT doc_type, product_name, standard_doc FROM certification_rules WHERE ? LIKE tnved_prefix || '%' ORDER BY length(tnved_prefix) DESC LIMIT 5",
                (tnved_code,)
            )
            if rows:
                lines = ["✅ **Найдено в официальных перечнях РФ:**"]
                seen = set()
                for r in rows:
                    key = (r['doc_type'], r['product_name'])
                    if key in seen: continue
                    seen.add(key)
                    
                    icon = "📜" if "Декларация" in r['doc_type'] else "🛡️"
                    lines.append(f"{icon} **{r['doc_type']}**: {r['product_name']}")
                    if r['standard_doc']:
                         # Shorten doc string if too long
                         doc_short = r['standard_doc'][:100] + "..." if len(r['standard_doc']) > 100 else r['standard_doc']
                         lines.append(f"   📄 _{doc_short}_")
                
                lines.append("\n👉 **Проверить точно:**")
                lines.append("[Единый реестр ЕЭК](https://eec.eaeunion.org/comission/department/deptexreg/tr/TR_general.php)")
                return "\n".join(lines)

        # 2. AI Fallback
        prompt = (
            f"Ты — профессиональный консультант по ВЭД. Твоя задача — определить ВЕРОЯТНЫЕ требования к сертификации.\n"
            f"Товар: «{query}».\n\n"
            "1. Перечисли ТР ТС (Технические регламенты), под которые МОЖЕТ подпадать этот товар. (Например, ТР ТС 004/2011, 020/2011, 017/2011 и др.)\n"
            "2. Укажи форму подтверждения: Сертификат или Декларация (если очевидно).\n"
            "3. Если товар скорее всего НЕ подлежит обязательной сертификации (или нужно Отказное письмо), укажи это.\n\n"
            "ВАЖНО: Ты должен явно предупредить, что список может быть неполным.\n"
            "ОБЯЗАТЕЛЬНО начни ответ с фразы: **«⚠️ Справочная информация (AI). В базе официальных перечней точного совпадения не найдено.»**\n\n"
            "Используй форматирование (жирный шрифт, списки).\n"
            "В конце ответа ВСЕГДА добавляй:\n"
            "👉 **Где проверить точно:**\n"
            "[Единый реестр ЕЭК](https://eec.eaeunion.org/comission/department/deptexreg/tr/TR_general.php) | [Реестр Росаккредитации](https://pub.fsa.gov.ru/rss/certificate)"
        )

        
        try:
            print(f"[LLM-Cert] Calling {model} for: '{query}'")
            resp = await self.aclient.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1 # Lower temperature for less creativity
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"[LLM-Cert] Error: {e}")
            return "⚠️ Ошибка при запросе к AI сервису сертификации. Попробуйте позже."

