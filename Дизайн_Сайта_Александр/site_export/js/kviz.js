$(function () {
  const steps = $('.quiz-step');
  const totalSteps = steps.length;
  const userAnswers = {};
  let currentIndex = 0;

  function updateProgress(index) {
    const percent = totalSteps > 1 ? (index / (totalSteps - 1)) * 100 : 100;
    $('.progress-fill').css('width', percent + '%');
  }

  function showStep(index) {
    steps.removeClass('active').hide();
    const $target = steps.eq(index);
    $target.show().addClass('active');
    currentIndex = index;
    updateProgress(index);
  }

  function collectAnswer(stepId, $inputs) {
    const type = ($inputs[0] || {}).type;
    if (type === 'radio') {
      const selected = $inputs.filter(':checked');
      if (!selected.length) {
        alert('Пожалуйста, выберите ответ.');
        return null;
      }
      return selected.val();
    }

    if (type === 'text' || type === 'tel') {
      const value = $inputs.val().trim();
      if (!value) {
        alert('Пожалуйста, заполните поле.');
        return null;
      }
      return value;
    }

    return null;
  }

  $('.next-btn, .call_btn_send').on('click', function () {
    const $step = $(this).closest('.quiz-step');
    const stepIdx = steps.index($step);
    const stepId = Number($step.data('step'));
    const $inputs = $step.find(`input[name="question${stepId}"]`);

    if ($inputs.length) {
      const answer = collectAnswer(stepId, $inputs);
      if (answer === null && stepIdx < totalSteps - 1) {
        return;
      }
      if (answer !== null) {
        userAnswers[stepId] = answer;
        evObj.userAnsw = userAnswers;
      }
    }

    if (stepIdx < totalSteps - 1) {
      showStep(stepIdx + 1);
    }
  });

  $('.prev-btn').on('click', function () {
    if (currentIndex > 0) {
      showStep(currentIndex - 1);
    }
  });

  showStep(0);
});
