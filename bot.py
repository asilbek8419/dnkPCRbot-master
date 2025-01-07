import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.session.base import BaseSession
from fpdf import FPDF
import tempfile
import asyncio
import os  # Импортируем os для работы с переменными окружения

# Получаем токен из переменных окружения
token = os.getenv("BOT_TOKEN")

if not token:
    raise ValueError("Необходимо установить переменную окружения BOT_TOKEN.")

# Настройка логгирования
logging.basicConfig(level=logging.INFO)

# Создаем бота и диспетчер
bot = Bot(token=token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Глобальные переменные для хранения данных
researches = {}  # Хранит данные для нескольких исследований
rows = ["A", "B", "C", "D", "E", "F", "G", "H"]

# Определение состояний
class ResearchStates(StatesGroup):
    waiting_for_research_name = State()
    waiting_for_data = State()
    waiting_for_research_to_close = State()
    waiting_for_research_to_print = State()

def display_plate_as_table(plate):
    """Функция для отображения плашки в табличном формате."""
    column_width = 8  # Определяем фиксированную ширину для каждой ячейки
    table = "|   | " + " | ".join(f"{i+1:^{column_width}}" for i in range(12)) + " |\n"
    table += "|---" + ("|---" * 12) + "|\n"
    for i, row in enumerate(rows):
        row_data = " | ".join(f"{plate[i][j]:^{column_width}}" if plate[i][j] else "-".center(column_width) for j in range(12))
        table += f"| {row} | {row_data} |\n"
    return table

def add_objects_to_plate(plate, expertise, object_count, object_numbers):
    """Функция для добавления объектов на плашку по вертикали."""
    index = 0
    for j in range(12):  # Столбцы 1-12
        for i in range(8):  # Строки A-H
            if plate[i][j] == "":
                if index < object_count:
                    plate[i][j] = f"{expertise}-{object_numbers[index]}"
                    index += 1
                else:
                    return "Объекты успешно добавлены."
    return "Плашка заполнена, не удалось добавить все объекты."

def generate_pdf(plate_text):
    """Функция для генерации PDF с плашкой."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="96-луночная плашка", ln=True, align="C")
    pdf.ln(10)

    for line in plate_text.split("\n"):
        pdf.cell(200, 10, txt=line, ln=True)

    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, "plate.pdf")
    pdf.output(file_path)
    return file_path

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "Привет! Я бот для управления 96-луночной плашкой.\n"
        "Команды:\n"
        "/new_research - начать новое исследование\n"
        "/add_objects - добавить объекты на плашку\n"
        "/show_researches - показать активные исследования\n"
        "/close_research - завершить исследование\n"
        "/print_plate - вывести плашку в PDF"
    )

@dp.message(Command("new_research"))
async def new_research_command(message: types.Message, state: FSMContext):
    await message.answer("Введите название нового исследования:")
    await state.set_state(ResearchStates.waiting_for_research_name)

@dp.message(ResearchStates.waiting_for_research_name)
async def set_research_name(message: types.Message, state: FSMContext):
    research_name = message.text.strip()
    if research_name in researches:
        await message.answer("Исследование с таким названием уже существует. Попробуйте другое название.")
        return

    researches[research_name] = [["" for _ in range(12)] for _ in range(8)]
    await state.clear()
    await message.answer(f"Новое исследование '{research_name}' начато.")

@dp.message(Command("add_objects"))
async def add_objects_command(message: types.Message):
    if not researches:
        await message.answer("Нет активных исследований. Сначала создайте исследование с помощью команды /new_research.")
        return

    await message.answer(
        "Введите данные в формате:\n"
        "<название исследования> <номер экспертизы> <количество объектов> <номера объектов через запятую>\n"
        "Пример: VersaPlex 16654 3 1,5,6"
    )

@dp.message(lambda message: len(message.text.split()) >= 4)
async def process_add_objects(message: types.Message):
    try:
        research_name, expertise, object_count, object_numbers = message.text.split(maxsplit=3)
        object_count = int(object_count)
        object_numbers = object_numbers.split(",")

        if research_name not in researches:
            await message.answer("Такого исследования не существует. Проверьте название.")
            return

        if len(object_numbers) != object_count:
            await message.answer("Количество объектов не совпадает с указанным числом.")
            return

        plate = researches[research_name]
        response = add_objects_to_plate(plate, expertise, object_count, object_numbers)
        await message.answer(response)
    except Exception as e:
        await message.answer("Ошибка: проверьте формат ввода данных.")

@dp.message(Command("show_researches"))
async def show_researches_command(message: types.Message):
    if not researches:
        await message.answer("Нет активных исследований.")
        return

    response = "Активные исследования:\n"
    for research_name, plate in researches.items():
        response += f"\nИсследование: {research_name}\n"
        response += display_plate_as_table(plate)
    await message.answer(f"<pre>{response}</pre>", parse_mode="HTML")

@dp.message(Command("close_research"))
async def close_research_command(message: types.Message, state: FSMContext):
    if not researches:
        await message.answer("Нет активных исследований.")
        return

    await message.answer("Введите название исследования, которое хотите завершить:")
    await state.set_state(ResearchStates.waiting_for_research_to_close)

@dp.message(ResearchStates.waiting_for_research_to_close)
async def process_close_research(message: types.Message, state: FSMContext):
    research_name = message.text.strip()
    if research_name not in researches:
        await message.answer("Такого исследования не существует. Проверьте название.")
        return

    plate = researches.pop(research_name)
    plate_text = display_plate_as_table(plate)
    await state.clear()
    await message.answer(f"Исследование '{research_name}' завершено. Итоговая плашка:\n<pre>{plate_text}</pre>", parse_mode="HTML")

@dp.message(Command("print_plate"))
async def print_plate_command(message: types.Message, state: FSMContext):
    if not researches:
        await message.answer("Нет активных исследований для печати.")
        return

    await message.answer("Введите название исследования для печати:")
    await state.set_state(ResearchStates.waiting_for_research_to_print)

@dp.message(ResearchStates.waiting_for_research_to_print)
async def process_print_plate(message: types.Message, state: FSMContext):
    research_name = message.text.strip()
    if research_name not in researches:
        await message.answer("Такого исследования не существует. Проверьте название.")
        return

    plate = researches[research_name]
    plate_text = display_plate_as_table(plate)
    file_path = generate_pdf(plate_text)
    await state.clear()
    with open(file_path, "rb") as pdf_file:
        await message.answer_document(pdf_file)

async def main():
    async with bot:
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
