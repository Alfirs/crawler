from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.domain.calculator import Calculator, CalculatorInput
from app.domain.rates import RatesStore
from app.domain.validation import validate_input
from app.flow.detectors import InputDetector, InputType
from app.flow.loader import ActionType, BotMap, Button, Edge, Node, ScreenType
from app.flow.signatures import normalize_action_text, normalize_text
from app.storage.models import SessionState


class KeyboardType(str, Enum):
    INLINE = "inline"
    REPLY = "reply"
    NONE = "none"


@dataclass(frozen=True)
class RenderedScreen:
    node_id: str
    text: str
    buttons: list[list[Button]]
    keyboard: KeyboardType
    screen_type: ScreenType


@dataclass
class EngineResponse:
    session: SessionState
    rendered: RenderedScreen
    hints: list[str] = field(default_factory=list)
    extra_messages: list[str] = field(default_factory=list)
    action_type: ActionType | None = None
    action_value: str | None = None
    transitioned: bool = False

class FlowEngine:
    def __init__(
        self,
        bot_map: BotMap,
        detector: InputDetector,
        rates_store: RatesStore,
        default_keyboard_mode: str,
        raw_log: list[Any] | None = None,
        root_node_id: str | None = None,
        search_service: Any | None = None,
    ) -> None:
        self.bot_map = bot_map
        self.detector = detector
        self.default_keyboard_mode = default_keyboard_mode
        self.calculator = Calculator(rates_store)
        self.search_service = search_service
        self.graph = _FlowGraph(bot_map)
        self.root_node_id = root_node_id or self._select_root_node(raw_log or [])

    def start_session(self, user_id: int) -> SessionState:
        session = SessionState(user_id=user_id, current_node_id=self.root_node_id)
        self._ensure_pending_input(session)
        return session

    async def render(self, node_id: str, session: SessionState = None) -> RenderedScreen:
        node = self._get_node(node_id)
        
        # DYNAMIC GENERATION HOOK
        # If this is the "Search Result" node, we should generate it based on session data
        if node_id == "node_search_result" and session and self.search_service:
            # Get the user's search query (last input)
            # The session stores inputs in `data`. 
            # We need to find "name" or text input.
            # Search if we have a name
            query = session.data.get("name")
            if query:
                # SEARCH CALL
                results = await self.search_service.search(query)
                
                # Format results
                if not results:
                    text_lines = ["\u041a \u0441\u043e\u0436\u0430\u043b\u0435\u043d\u0438\u044e, \u043a\u043e\u0434 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0438\u0437\u043c\u0435\u043d\u0438\u0442\u044c \u0437\u0430\u043f\u0440\u043e\u0441."]
                    btns = []
                    return RenderedScreen(
                        node_id=node.id,
                        text="\n".join(text_lines),
                        buttons=btns,
                        keyboard=KeyboardType.INLINE,
                        screen_type=ScreenType.MENU
                    )
                else:    
                    # Generate dynamic node content
                    text = f"🔍 **Найдено {len(results)} вариантов кода ТНВЭД:**\n\n"
                    buttons = []
                    
                    for idx, res in enumerate(results, 1):
                        # Show duty with note if from AI
                        duty_note = "" if res.source != "ai" else " ≈"
                        text += f"{idx}. **Код {res.code}** ({res.duty_pct * 100:.0f}%{duty_note})\n   {res.description[:100]}...\n\n"
                        # Dynamic button with code
                        buttons.append([Button(text=f"Код {res.code}", url=None)])
                    
                    text += "Выберите наиболее подходящий код ТНВЭД:"
                    
                    return RenderedScreen(
                        node_id=node.id,
                        text=text,
                        buttons=buttons,
                        keyboard=KeyboardType.INLINE, # Search results usually inline
                        screen_type=ScreenType.MENU
                    )
                    
        keyboard = self._keyboard_for_node(node)
        return RenderedScreen(
            node_id=node.id,
            text=node.text,
            buttons=node.buttons,
            keyboard=keyboard,
            screen_type=node.screen_type,
        )

    async def handle_action(
        self,
        session: SessionState,
        action_type: ActionType,
        action_value: str,
    ) -> EngineResponse:
        current_node = self._get_node(session.current_node_id)
        hints: list[str] = []
        extra_messages: list[str] = []
        transitioned = False

        edge = self.graph.find_edge(current_node.id, action_type, action_value)
        if edge is None and action_type == ActionType.SEND_TEXT:
            edge = self.graph.find_edge(current_node.id, ActionType.CLICK, action_value)

        if edge:
            # Special handling for Auto Pick -> Searching
            # We want to Capture the text and Jump straight to Search Result
            if edge.from_node == "node_pick_auto":
                 session.data["name"] = action_value
                 # Skip 'node_searching' which is just a text placeholder
                 session.current_node_id = "node_search_result"
            else:
                session.current_node_id = edge.to_node

            transitioned = True
            session.pending_input_type = None
            current_node = self._get_node(session.current_node_id)
        else:
            # SMART ROUTING FOR ROOT NODE
            # If we are at root, and user sent text, try to route based on content
            if current_node.id == self.root_node_id and action_type == ActionType.SEND_TEXT:
                # Ignore commands that fell through
                if action_value.startswith("/"):
                    return EngineResponse(session, self.render(session.current_node_id, session)) # No change

                # Detect what it is
                input_type = self.detector.detect_input_type(action_value)
                
                # If it looks like a TNVED code (10 digits)
                if input_type == InputType.NUMBER and len(action_value.strip()) == 10:
                    # Direct code entry: Skip search and go straight to price input
                    session.data["tnved_code"] = action_value.strip()
                    session.data["selected_code"] = action_value.strip()
                    session.data["duty_pct"] = 10.0  # Default duty, can be overridden later
                    session.current_node_id = "node_enter_price"
                    transitioned = True
                    
                # If it looks like text (Name) - do AI search
                elif input_type == InputType.TEXT or input_type == InputType.NAME:
                     session.data["name"] = action_value
                     session.current_node_id = "node_search_result"
                     transitioned = True

            # ALSO handle text input on search result screen (for new searches)
            elif current_node.id == "node_search_result" and action_type == ActionType.SEND_TEXT:
                if not action_value.startswith("/"):
                    input_type = self.detector.detect_input_type(action_value)
                    if input_type == InputType.TEXT or input_type == InputType.NAME:
                        # New search query
                        session.data["name"] = action_value
                        # Stay on search result, but will re-render with new query
                        transitioned = True

            if not transitioned:
                if current_node.screen_type == ScreenType.INPUT_REQUIRED:
                    hint, extra = await self._handle_input(session, current_node, action_value)
                    if hint:
                        hints.append(hint)
                    else:
                        # Input was accepted, so we effectively transitioned (or at least processed it statefully)
                        transitioned = True
                    
                    if extra:
                        extra_messages.append(extra)
                else:
                    # Only show error if we really stuck
                    if not transitioned:
                        hints.append("Action not recognized. Use the buttons or valid input.")

        self._ensure_pending_input(session)
        rendered = await self.render(session.current_node_id, session)
        
        return EngineResponse(
            session=session,
            rendered=rendered,
            hints=hints,
            extra_messages=extra_messages,
            action_type=action_type,
            action_value=action_value,
            transitioned=transitioned,
        )

    async def _handle_input(
        self,
        session: SessionState,
        node: Node,
        user_text: str,
    ) -> tuple[str | None, str | None]:
        input_type = self._resolve_input_type(session, node)
        validation = validate_input(input_type, user_text)
        if not validation.ok:
            return self.detector.format_hint(input_type), None

        field_key = _field_for_input(input_type, node.text)
        session.data[field_key] = validation.value
        session.last_prompt = node.text

        next_node = self.graph.pick_next_node(node.id)
        if next_node:
            session.current_node_id = next_node
            session.pending_input_type = None

        extra_message = await self._maybe_calculate(node, session)
        return None, extra_message

    async def _maybe_calculate(self, node: Node, session: SessionState) -> str | None:
        if not self.detector.should_calculate(node.text, session.data):
            return None
        
        def _safe_float(val: Any) -> float:
            """Safely convert to float, returning 0.0 for invalid values."""
            if val is None:
                return 0.0
            try:
                # Handle Russian comma decimal separator
                if isinstance(val, str):
                    val = val.replace(",", ".")
                return float(val)
            except (ValueError, TypeError):
                return 0.0
        
        weight = _safe_float(session.data.get("weight_kg"))
        volume = _safe_float(session.data.get("volume_m3"))
        
        # Calculate volume from dimensions if present
        l = _safe_float(session.data.get("length_cm"))
        w = _safe_float(session.data.get("width_cm"))
        h = _safe_float(session.data.get("height_cm"))
        
        if l > 0 and w > 0 and h > 0:
            # Volume in m3 = (l*w*h) / 1,000,000
            volume = (l * w * h) / 1_000_000.0

        value = _safe_float(session.data.get("goods_value"))
        if value <= 0 or (weight <= 0 and volume <= 0):
            return None

        # Enrichment: If we have a TNVED code, try to find duty/category
        tnved_code = session.data.get("tnved_code")
        if tnved_code and self.search_service:
            # Quick lookup
            res = await self.search_service.search(str(tnved_code))
            if res:
                # Use the first exact match or best guess
                best = res[0]
                # Store duty explicitly for calculator if needed, or map to category
                # For now, let's just make sure "product_category" is set if missing
                if not session.data.get("product_category"):
                    session.data["product_category"] = best.description[:50]
                # TODO: Pass duty_pct to calculator if it supports it override
                
        data = CalculatorInput(
            product_category=_safe_text(session.data.get("product_category")),
            weight_kg=weight,
            volume_m3=volume,
            goods_value=value,
            origin=_safe_text(session.data.get("origin")),
            destination=_safe_text(session.data.get("destination")),
            urgency=_safe_text(session.data.get("urgency")),
        )
        result = await self.calculator.calculate(data)
        return self.calculator.render(result)

    def _resolve_input_type(self, session: SessionState, node: Node) -> InputType:
        if session.pending_input_type:
            try:
                return InputType(session.pending_input_type)
            except ValueError:
                pass
        return self.detector.detect_input_type(node.text)

    def _ensure_pending_input(self, session: SessionState) -> None:
        node = self._get_node(session.current_node_id)
        if node.screen_type != ScreenType.INPUT_REQUIRED:
            return
        if session.pending_input_type is None:
            input_type = self.detector.detect_input_type(node.text)
            session.pending_input_type = input_type.value
            session.last_prompt = node.text

    def _keyboard_for_node(self, node: Node) -> KeyboardType:
        if not node.buttons:
            return KeyboardType.NONE
        hint = self.detector.keyboard_hint(node.text)
        if hint == "inline":
            return KeyboardType.INLINE
        if hint == "reply":
            return KeyboardType.REPLY

        has_click = self.graph.has_edge_type(node.id, ActionType.CLICK)
        has_text = self.graph.has_edge_type(node.id, ActionType.SEND_TEXT)
        if has_click:
            return KeyboardType.INLINE
        if has_text:
            return KeyboardType.REPLY
        if any(btn.url for row in node.buttons for btn in row):
            return KeyboardType.INLINE
        return KeyboardType(self.default_keyboard_mode)

    def _select_root_node(self, raw_log: list[Any]) -> str:
        candidates = [node for node in self.bot_map.nodes.values() if not node.example_path]
        if candidates:
            candidates.sort(key=lambda n: n.created_at)
            return candidates[0].id

        first_prompt = _find_first_prompt(raw_log)
        if first_prompt:
            normalized = normalize_text(first_prompt)
            for node in self.bot_map.nodes.values():
                if normalize_text(node.text) == normalized:
                    return node.id

        if self.bot_map.nodes:
            return next(iter(self.bot_map.nodes))
        raise RuntimeError("Bot map has no nodes")

    def _get_node(self, node_id: str) -> Node:
        node = self.bot_map.nodes.get(node_id)
        if not node:
            raise KeyError(f"Unknown node: {node_id}")
        return node


class _FlowGraph:
    def __init__(self, bot_map: BotMap) -> None:
        self._edges_by_from: dict[str, list[Edge]] = {}
        self._index: dict[tuple[str, ActionType, str], Edge] = {}
        for edge in bot_map.edges:
            self._edges_by_from.setdefault(edge.from_node, []).append(edge)
            key = (edge.from_node, edge.action.type, normalize_action_text(edge.action.value))
            self._index[key] = edge

    def find_edge(self, from_node: str, action_type: ActionType, value: str) -> Edge | None:
        normalized = normalize_action_text(value)
        
        # 1. Exact match
        edge = self._index.get((from_node, action_type, normalized))
        if edge:
            return edge
            
        # 2. Wildcard match (__any__)
        wildcard_key = (from_node, action_type, "__any__")
        wildcard_edge = self._index.get(wildcard_key)
        if wildcard_edge:
            return wildcard_edge

        # 3. Partial match (legacy crawler fuzzy logic)
        for candidate in self._edges_by_from.get(from_node, []):
            if candidate.action.type != action_type:
                continue
            candidate_value = normalize_action_text(candidate.action.value)
            # Skip if candidate is wildcard to avoid false positives in partial logic
            if candidate.action.value == "__any__":
                continue
            if normalized and (normalized in candidate_value or candidate_value in normalized):
                return candidate
        return None

    def pick_next_node(self, from_node: str) -> str | None:
        edges = self._edges_by_from.get(from_node, [])
        if len(edges) == 1:
            return edges[0].to_node
        return None

    def has_edge_type(self, from_node: str, action_type: ActionType) -> bool:
        return any(
            edge.action.type == action_type for edge in self._edges_by_from.get(from_node, [])
        )


def _find_first_prompt(raw_log: list[Any]) -> str | None:
    for entry in raw_log:
        if getattr(entry, "event_type", None) in {"message_received", "message_edited"}:
            text = getattr(entry, "data", {}).get("text")
            if text:
                return str(text)
    return None


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _field_for_input(input_type: InputType, prompt: str) -> str:
    if input_type == InputType.WEIGHT_KG:
        return "weight_kg"
    if input_type == InputType.VOLUME_M3:
        return "volume_m3"
    if input_type == InputType.LENGTH_CM:
        return "length_cm"
    if input_type == InputType.WIDTH_CM:
        return "width_cm"
    if input_type == InputType.HEIGHT_CM:
        return "height_cm"
    if input_type == InputType.QUANTITY:
        return "quantity"
    if input_type == InputType.PRICE_VALUE:
        return "goods_value"
    if input_type == InputType.CITY:
        return "city"
    if input_type == InputType.NAME:
        return "name"
    if input_type == InputType.NUMBER:
        return "number"
    if "код" in prompt.lower() or "code" in prompt.lower():
        return "tnved_code"
    if "\u043a\u0430\u0442\u0435\u0433\u043e\u0440" in prompt.lower() or "category" in prompt.lower():
        return "product_category"
    return "text"
