

$(document).ready(function () {
	$('.btn_call_gg').on('click', function (e) {
    e.preventDefault();
		$('#popup_gg, .dark_bg').addClass('show');
	});
	$('.close-btn, .dark_bg').on('click', function () {
		closegg2();
	});
});

function closegg2() {
	$('#popup_gg, .dark_bg').removeClass('show');
}

$(document).ready(function () {
  const steps = $('.quiz-step');
  const totalSteps = steps.length;
  const userAnswers = {};

  function updateProgressBar(index) {
    const percent = ((index + 1) / totalSteps) * 100;
    $('.progress-fill').css('width', percent + '%');
  }

  function showStep(index) {
    const $current = $('.quiz-step.active');
    const $next = steps.eq(index);

    $current.animate({ opacity: 0 }, 300, function () {
      $current.removeClass('active').hide();
      $next.show().css('opacity', 0).addClass('active').animate({ opacity: 1 }, 300);
      updateProgressBar(index);

      if (index === totalSteps - 1) {
        renderAnswers();
      }
    });
  }

  function renderAnswers() {
    let output = '<ul>';
    for (let key in userAnswers) {
      output += `<li><strong>Вопрос ${parseInt(key)+1}:</strong> ${userAnswers[key]}</li>`;
    }
    output += '</ul>';
    $('#answers-output').html(output);
  }

  $('.next-btn,.call_btn_send').on('click', function () {
    const $currentStep = $(this).closest('.quiz-step');
    const currentIndex = steps.index($currentStep);
    const stepId = $currentStep.data('step');

    const $inputs = $currentStep.find(`input[name="question${stepId}"]`);
    let answer = null;
    const inputType = $inputs.attr('type');

    if (inputType === 'radio') {
      const selected = $inputs.filter(':checked');
      if (selected.length === 0 && currentIndex < totalSteps - 1) {
        alert("Пожалуйста, выберите ответ!");
        return;
      }
      answer = selected.val();
    } else if (inputType === 'text') {
      const textVal = $inputs.val().trim();
      if (!textVal && currentIndex < totalSteps - 1) {
        alert("Пожалуйста, введите значение!");
        return;
      }
      answer = textVal;
    }

    if (answer !== null) {
      userAnswers[stepId] = answer;
    }

    if (currentIndex < totalSteps - 1) {
      showStep(currentIndex + 1);
    }

  
    evObj.userAnsw = userAnswers;
      console.log(userAnswers,evObj.userAnsw );
  });

  $('.prev-btn').on('click', function () {
    const currentIndex = steps.index($('.quiz-step.active'));
    if (currentIndex > 0) {
      showStep(currentIndex - 1);
    }
  });

  // Инициализация
  updateProgressBar(0);
});
