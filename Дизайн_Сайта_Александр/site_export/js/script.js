// let form__tel_message_number = 12;
let evObj = {
	userAnsw: {},
};

$(document).ready(function () {

	$('input[name="name"]').inputmask({
		placeholder: "",
		regex: "[а-яА-ЯеЁa-zA-Z/0-9/Ññá¡/ ]{30}"
	});
	$('input[name="phone"]').inputmask({
		placeholder: "",
		regex: "[0-9]{20}"
	});

	// $('input[name="phone"]').inputmask("+375-99-999-99-99[9][9][9]", {
	// 	optionalmarker: ["[", "]"]
	// });







});


