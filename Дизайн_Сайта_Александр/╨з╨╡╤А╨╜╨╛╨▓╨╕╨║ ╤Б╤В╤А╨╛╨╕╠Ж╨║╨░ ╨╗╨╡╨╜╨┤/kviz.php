  <div class="quiz-container">

          <!-- Прогресс-бар -->
          <div class="progress-bar">
            <div class="progress-fill" style="width: 50%;"></div>
          </div>

          <!-- Шаг 1 -->
          <div class="quiz-step active" data-step="0">
            <h2>Вопрос 1</h2>
            <p>Гидроизоляция какого объета вам нужна?</p>
            <div class="quiz-step_radio_cont">
              <label for="question01"><input name="question0" id="question01" type="radio" required value="крыша"> крыша</label>
              <label for="question02"><input name="question0" id="question02" type="radio" required value="фундамент"> фундамент</label>
              <label for="question03"><input name="question0" id="question03" type="radio" required value="бассейн"> бассейн</label>
              <label for="question04"><input name="question0" id="question04" type="radio" required value="другое"> другое</label>
            </div>
            <div class="btn-row">
              <button class="next-btn">Далее</button>
            </div>
          </div>

          <!-- Шаг 2 -->
          <div class="quiz-step " data-step="1">
            <h2>Вопрос 2</h2>
            <p>Какая площадь объекта?</p>
            <div class="quiz-step_radio_cont">
              <label for="question11"><input name="question1" id="question11" type="radio" required value="до 50 кв м">до 50 кв м</label>
              <label for="question12"><input name="question1" id="question12" type="radio" required value="50-150 кв м">50-150 кв м</label>
              <label for="question13"><input name="question1" id="question13" type="radio" required value="от 150 кв м">от 150 кв м</label>
            </div>
            <div class="btn-row">
              <button class="prev-btn">Назад</button>
              <button class="next-btn">Далее</button>
            </div>
          </div>

          <!-- Шаг 3 -->
          <div class="quiz-step " data-step="2">
            <h2>Вопрос 3</h2>
            <p>Нужно отремонтировать старую гироизоляцию или делаем с новую?</p>
            <div class="quiz-step_radio_cont">
              <label for="question21"><input name="question2" id="question21" type="radio" required value="Только ремонт">Только ремонт</label>
              <label for="question22"><input name="question2" id="question22" type="radio" required value="Гидроизоляции нет, делаем с нуля">Гидроизоляции нет, делаем с нуля</label>
            </div>
            <div class="btn-row">
              <button class="prev-btn">Назад</button>
              <button class="next-btn">Далее</button>
            </div>
          </div>

          <!-- Шаг 4 -->
          <div class="quiz-step " data-step="3">
            <h2>Вопрос 4</h2>
             <p>Как срочно нужно выполнить задачу?</p>
            <div class="quiz-step_radio_cont">
              <label for="question31"><input name="question3" id="question31" type="radio" required value="Уже сейчас (срочно)">Уже сейчас (срочно)</label>
              <label for="question32"><input name="question3" id="question32" type="radio" required value="В течении месяца">В течении месяца</label>
              <label for="question33"><input name="question3" id="question33" type="radio" required value="В ближайшие 3 месяца">В ближайшие 3 месяца</label>
            </div>
            <div class="btn-row">
              <button class="prev-btn">Назад</button>
              <button class="next-btn">Далее</button>
            </div>
          </div>


             <!-- ФОРМА -->
          <div class="quiz-step" data-step="4">
            <h2>Последний шаг</h2>
            <p>Заполните форму, чтобы получить расчёт стоимости гидроизоляции + закрепить акцию на скидку 10%</p>
            <div class="quiz-step__form_ctn">
              <form id="order">

                <input type="hidden" name="msg" id="quiz-step__form_ctn__msg">



                <div class="form__tel">
                  <input type="text" class="" placeholder="Имя" id="name1" name="name" required="" autocomplete="off"
                    inputmode="text">
                  <div class="form__name_message invisible opacityNone"></div>
                </div>

                <div class="form__tel">
                  <input class="" type="tel" placeholder="Номер телефона" id="phone1" required="" autocomplete="off"
                    name="phone" inputmode="text">
                  <div class="form__tel_message invisible opacityNone"></div>
                </div>


                <button class="quiz-step__form_ctn__btn" type="submit" id="btn1">Отправить заявку</button>

                <div class="quiz-step__form_ctn__success invisible opacityNone">Отправлено!</div>

              </form>
            </div>
            <div class="btn-row">
              <button class="prev-btn">Назад</button>
              <!-- <button class="next-btn">Далее</button> -->
            </div>
          </div>



        </div>