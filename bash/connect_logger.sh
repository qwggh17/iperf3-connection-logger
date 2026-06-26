
#!/bin/bash

# Предопределенные переменные
SERVER_IP="$1"
PORT="$2"

LOG_FILE="$(dirname "$0")/connect_log.txt"

TIMEOUT_SECONDS=120
TEST_DURATION=1
SLEEP_SECONDS=1

# Проверка аргументов
if [ "$#" -ne 2 ]; then
    echo "Использование: $0 <IP-адрес> <порт>"
    echo "Пример: $0 192.168.1.82 4444"
    exit 1
fi

# Создание файла лога, если его нет
touch "$LOG_FILE"

echo "======================================" >> "$LOG_FILE"
echo "Запуск скрипта: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "Сервер: $SERVER_IP" >> "$LOG_FILE"
echo "Порт: $PORT" >> "$LOG_FILE"
echo "======================================" >> "$LOG_FILE"

echo "Логирование запущено."
echo "Сервер: $SERVER_IP"
echo "Порт: $PORT"
echo "Лог пишется в файл: $LOG_FILE"
echo "Для остановки нажми Ctrl+C"

while true
do
    CURRENT_TIME=$(date '+%Y-%m-%d %H:%M:%S')

    RESULT=$(timeout "$TIMEOUT_SECONDS" iperf3 -c "$SERVER_IP" -p "$PORT" -t "$TEST_DURATION" 2>&1)
    EXIT_CODE=$?

    if [ "$EXIT_CODE" -eq 0 ]; then

    SPEED=$(echo "$RESULT" | grep -i "receiver" | tail -n 1)

    {
        echo "[$CURRENT_TIME]"
        echo "Статус: OK"
        echo "IP: $SERVER_IP"
        echo "Порт: $PORT"
        echo "Скорость: $SPEED"
        echo "--------------------------------------------------"
    } >> "$LOG_FILE"

else

    {
        echo "[$CURRENT_TIME]"
        echo "Статус: ERROR"
        echo "IP: $SERVER_IP"
        echo "Порт: $PORT"
        echo "Причина: $RESULT"
        echo "--------------------------------------------------"
    } >> "$LOG_FILE"

fi

   sleep "$SLEEP_SECONDS"

done
