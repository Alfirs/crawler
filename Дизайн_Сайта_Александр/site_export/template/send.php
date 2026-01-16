<?php


function replaceSubstring($inStr, $strToFind, $strToReplace)
{
    $result = str_replace($strToFind, $strToReplace, $inStr);
    return $result;
}

if ($_SESSION['send'] == false) {



    $comment = replaceSubstring($_POST['msg'], "|", "\n");
    $name = $_POST['name'];
    $phone = $_POST['phone'];
    // Токен вашего Telegram бота
    $botToken = "8130056132:AAFSd_PsvPz30XHTgY3P_4BtsEhaWzhfRLw";

    // ID чата или username получателя
    $chatId = "-1002869859695";

    // Текст сообщения
    $message = "\n\nИмя: $name\nНомер: $phone\n\nКомментарии:\n$comment";

    // URL для отправки сообщения через Telegram API
    $url = "https://api.telegram.org/bot{$botToken}/sendMessage";

    // Параметры сообщения
    $data = [
        'chat_id' => $chatId,
        'text' => $message,
        "disable_web_page_preview" => true,
    ];

    // Инициализация cURL сессии
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

    // Выполнение запроса
    $response = curl_exec($ch);
    $arr = json_decode($response, true);
    // Закрытие cURL сессии
    curl_close($ch);

    // Проверка ответа от Telegram API
    if ($response) {
        echo "Сообщение отправлено успешно!";
        $_SESSION['send'] = true;
    } else {
        echo "Ошибка при отправке сообщения!";
    }

    date_default_timezone_set('Europe/Minsk');
    $datePost = date("Y-m-d__H:i:s");
    file_put_contents('leads.txt', $datePost . '  |  name - ' . $name . '  |  phone - ' . $phone  . '  |  comment - ' . $comment .  '  |  response - ' . $arr['ok'] . "\r\n", FILE_APPEND | LOCK_EX);
}
