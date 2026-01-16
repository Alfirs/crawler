// Подключение AOS
AOS.init({
    duration: 800,
    once: true
});

// Плавная прокрутка для меню
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetId = link.getAttribute('href').substring(1);
        const targetElement = document.getElementById(targetId);
        if (targetElement) {
            window.scrollTo({
                top: targetElement.offsetTop - 80,
                behavior: 'smooth'
            });
        }
    });
});

// Эффект печатной машинки
const phrases = ["Telegram", "VK", "WhatsApp"];
let currentPhrase = 0;
let charIndex = 0;
let isDeleting = false;
const element = document.querySelector(".glow");

function typeWriter() {
    const currentText = phrases[currentPhrase];
    element.textContent = currentText.substring(0, charIndex);

    if (!isDeleting) {
        charIndex++;
        if (charIndex > currentText.length) {
            isDeleting = true;
            setTimeout(typeWriter, 1500);
            return;
        }
    } else {
        charIndex--;
        if (charIndex === 0) {
            isDeleting = false;
            currentPhrase = (currentPhrase + 1) % phrases.length;
        }
    }

    setTimeout(typeWriter, isDeleting ? 100 : 200);
}

if (element) typeWriter();

// Частицы в hero
particlesJS("particles-js", {
    particles: {
        number: { value: 60, density: { enable: true, value_area: 800 } },
        color: { value: ["#a945ff", "#00cc99"] },
        shape: { type: "circle" },
        opacity: { value: 0.3, random: true },
        size: { value: 2, random: true },
        line_linked: { enable: true, distance: 120, color: "#a945ff", opacity: 0.2, width: 1 },
        move: { enable: true, speed: 1.5, direction: "none", random: true }
    },
    interactivity: {
        detect_on: "canvas",
        events: { onhover: { enable: true, mode: "repulse" }, onclick: { enable: true, mode: "push" } },
        modes: { repulse: { distance: 80, duration: 0.4 }, push: { particles_nb: 3 } }
    }
});

// Валидация формы
const nameInput = document.getElementById("name");
const phoneInput = document.getElementById("phone");

nameInput.addEventListener("input", () => {
    nameInput.value = nameInput.value.replace(/[^a-zA-Zа-яА-Я\s]/g, "");
});

phoneInput.addEventListener("input", () => {
    phoneInput.value = phoneInput.value.replace(/[^0-9+()-]/g, "");
});

// Отправка формы через Formspree
document.getElementById("contact-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const name = document.getElementById("name").value.trim();
    const phone = document.getElementById("phone").value.trim();
    const message = document.getElementById("message").value.trim();

    if (!name || !phone) {
        alert("Пожалуйста, заполните имя и телефон.");
        return;
    }

    const formData = new FormData();
    formData.append("name", name);
    formData.append("phone", phone);
    formData.append("message", message);
    formData.append("bonus", "1 месяц сопровождения бесплатно");

    try {
        console.log("Отправка заявки на почту...", { name, phone, message });
        const response = await fetch(form.action, {
            method: "POST",
            body: formData,
            headers: {
                "Accept": "application/json"
            }
        });

        if (response.ok) {
            console.log("Заявка отправлена на почту!");
            alert("Заявка отправлена! Скоро свяжемся.");
            form.reset();
        } else {
            const errorText = await response.text();
            console.error("Ошибка:", errorText);
            throw new Error(`Ошибка ${response.status}: ${errorText}`);
        }
    } catch (error) {
        console.error("Ошибка:", error.message);
        alert("Ошибка отправки. Проверьте Formspree ID или попробуйте позже.");
    }
});