// Scroll
// $(document).ready(function () {
// 	$("a[href^='#'], [data-href]").click(function (e) {
// 		if ($(this).attr('href') === '#') {
// 			e.preventDefault();
// 		} else {
// 			var _href = $(this).attr("href");
// 			$("html, body").animate({
// 				scrollTop: $(_href).offset().top + "px"
// 			});
// 			return false;
// 		}
// 	});
// });

// Дата
function pushDateAll(d) {
	let now = new Date();
	now.setDate(now.getDate() + d);
	let mm = now.getMonth() + 1;
	let day = now.getDate();
	if (now.getDate() < 10) day = '0' + now.getDate();
	if (mm < 10) mm = '0' + mm;

	jQuery('.date-yyyy').text(now.getFullYear());
	jQuery('.date-mm_yyyy').text(mm + "." + now.getFullYear());
	jQuery('.date-dd_mm_yyyy').text(day + "." + mm + "." + now.getFullYear());
}
pushDateAll(0);

function pushDate(d, format) {
	let now = new Date();
	now.setDate(now.getDate() + d);
	let mm = now.getMonth() + 1;
	let day = now.getDate();
	if (now.getDate() < 10) day = '0' + now.getDate();
	if (mm < 10) mm = '0' + mm;

	if (format == 'yyyy') {
		document.write(now.getFullYear())
	}
	if (format == 'dd_mm_yyyy') {
		document.write(day + "." + mm + "." + now.getFullYear())
	}
	if (format == 'mm_yyyy') {
		document.write(mm + "." + now.getFullYear())
	}
	if (format == 'dd_mm') {
		document.write(day + "." + mm)
	}
}
/* <script>pushDate(0, 'dd_mm_yyyy')</script> */

function pushTime(hour, minute) {
	let now = new Date();
	now.setMinutes(now.getMinutes() + minute);
	now.setHours(now.getHours() + hour);
	let mm = now.getMinutes();
	let hh = now.getHours();
	if (hh < 10) hh = '0' + hh;
	if (mm < 10) mm = '0' + mm;
	document.write(' ' + hh + ":" + mm);
}