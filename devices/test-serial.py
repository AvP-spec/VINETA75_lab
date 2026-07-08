import serial
import time

# Открываем порт напрямую через pyserial
try:
    ser = serial.Serial(
        port='COM15',
        baudrate=9600,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=3 # 3 секунды ожидания
    )
    print("Порт COM15 успешно открыт напрямую!")
    
    # Очищаем буферы
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    
    # Отправляем команду ID с терминатором \r\n (символы перевода строки)
    # Переводим строку в байты (b'...')
    ser.write(b"ID\r\n")
    print("Команда 'ID' отправлена. Ждем ответ...")
    
    # Читаем ответ до терминатора \n
    time.sleep(0.1)
    response = ser.readline()
    
    # Декодируем байты обратно в текст
    print(f"Сырой ответ прибора (bytes): {response}")
    print(f"Текстовый ответ: {response.decode('utf-8').strip()}")
    
    ser.close()

except Exception as e:
    print(f"Ошибка прямого подключения: {e}")