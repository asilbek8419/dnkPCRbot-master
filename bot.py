import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from tabulate import tabulate
from fpdf import FPDF
import tempfile
import asyncio
import os

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
researches = {}
rows = ["A", "B", "C", "D", "E", "F", "G", "H"]

# Клавиатура с командами
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/obyekt_qushish"), KeyboardButton(text="/tadqiqotlarni_kurish")],
        [KeyboardButton(text="/yangi_tadqiqot"), KeyboardButton(text="/tadqiqotni_yakunlash")],
        [KeyboardButton(text="/plashkani_chop_etish")]
    ],
    resize_keyboard=True
)

# Определение состояний
class ResearchStates(StatesGroup):
    waiting_for_research_name = State()
    waiting_for_data = State()
    waiting_for_research_to_close = State()
    waiting_for_research_to_print = State()

def display_plate_as_table(plate):
    """Функция для отображения плашки в табличном формате."""
    table_data = [[cell if cell else "-" for cell in row] for row in plate]
    table = tabulate(table_data, headers=[str(i + 1) for i in range(12)], tablefmt="grid", showindex=rows)
    return table

def obyekt_qushish_to_plate(plate, expertise, object_count, object_numbers):
    """Функция для добавления объектов на плашку по вертикали."""
    index = 0
    for j in range(12):  # Столбцы 1-12
        for i in range(8):  # Строки A-H
            if plate[i][j] == "":
                if index < object_count:
                    plate[i][j] = f"{expertise}-{object_numbers[index]}"
                    index += 1
                else:
                    return "Объектлар муваффаққиятли юкланди."
    return "Плашка тўла, объектларни қўшиш имкони бўлмади."

def generate_pdf(plate_text):
    """Функция для генерации PDF с плашкой."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="96-лункали плашка", ln=True, align="C")
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
        "Ассалому алейкум! Мен 96-лункали плашкани бошқариш ботиман. Амални танланг:",
        reply_markup=main_keyboard
    )

@dp.message(Command("yangi_tadqiqot"))
async def yangi_tadqiqot_command(message: types.Message, state: FSMContext):
    await message.answer("Янги тадқиқот номини ёзинг:")
    await state.set_state(ResearchStates.waiting_for_research_name)

@dp.message(ResearchStates.waiting_for_research_name)
async def set_research_name(message: types.Message, state: FSMContext):
    research_name = message.text.strip()
    if research_name in researches:
        await message.answer("Бундай тадқиқот номи мавжуд. Бошқа ном киритинг.")
        return

    researches[research_name] = [["" for _ in range(12)] for _ in range(8)]
    await state.clear()
    await message.answer(f"Янги тадқиқот '{research_name}' бошланди.")

@dp.message(Command("obyekt_qushish"))
async def obyekt_qushish_command(message: types.Message):
    if not researches:
        await message.answer("Актив тадқиқотлар йўқ. Аввало янги тадқиқотни қўйидаги команда орқали бошланг /yangi_tadqiqot.")
        return

    await message.answer(
        "Маълумотларни қўйидаги форматда киритинг:\n"
        "<Тадқиқот номи> <экспертиза рақами> <объектлар сони> <объектлар номи вергуль билан>\n"
        "Мисол: Верса AN16654 3 K1,C5,L6"
    )

@dp.message(lambda message: len(message.text.split()) >= 4)
async def process_obyekt_qushish(message: types.Message):
    try:
        research_name, expertise, object_count, object_numbers = message.text.split(maxsplit=3)
        object_count = int(object_count)
        object_numbers = object_numbers.split(",")

        if research_name not in researches:
            await message.answer("Бундай тадқиқот мавжуд эмас. Тадқиқот номини текширинг.")
            return

        if len(object_numbers) != object_count:
            await message.answer("Объектлар сони келтирилган рақамга тўғри келмади.")
            return

        plate = researches[research_name]
        response = obyekt_qushish_to_plate(plate, expertise, object_count, object_numbers)
        await message.answer(response)
    except Exception as e:
        await message.answer("ХАТО: маълумотларни киритиш тартибини текширинг.")

@dp.message(Command("tadqiqotlarni_kurish"))
async def tadqiqotlarni_kurish_command(message: types.Message):
    if not researches:
        await message.answer("Актив тадқиқотлар йўқ.")
        return

    response = "Актив тадқиқотлар:\n"
    for research_name, plate in researches.items():
        response += f"\nТадқиқот: {research_name}\n"
        response += display_plate_as_table(plate) + "\n"
    await message.answer(f"<pre>{response}</pre>", parse_mode="HTML")

@dp.message(Command("tadqiqotni_yakunlash"))
async def tadqiqotni_yakunlash_command(message: types.Message, state: FSMContext):
    if not researches:
        await message.answer("Актив тадқиқотлар йўқ.")
        return

    await message.answer("Тугатилаётган тадқиқот номини ёзинг:")
    await state.set_state(ResearchStates.waiting_for_research_to_close)

@dp.message(ResearchStates.waiting_for_research_to_close)
async def process_tadqiqotni_yakunlash(message: types.Message, state: FSMContext):
    research_name = message.text.strip()
    if research_name not in researches:
        await message.answer("Бундай тадқиқот мавжуд эмас. Тадқиқот номини текширинг.")
        return

    plate = researches.pop(research_name)
    plate_text = display_plate_as_table(plate)
    await state.clear()
    await message.answer(f"Тадқиқот '{research_name}' тугатилди. Якуний плашка:\n<pre>{plate_text}</pre>", parse_mode="HTML")

@dp.message(Command("plashkani_chop_etish"))
async def plashkani_chop_etish_command(message: types.Message, state: FSMContext):
    if not researches:
        await message.answer("Чоп этишга актив тадқиқотлар мавжуд эмас.")
        return

    await message.answer("Чоп этиладиган тадқиқот номини ёзинг:")
    await state.set_state(ResearchStates.waiting_for_research_to_print)

@dp.message(ResearchStates.waiting_for_research_to_print)
async def process_plashkani_chop_etish(message: types.Message, state: FSMContext):
    research_name = message.text.strip()
    if research_name not in researches:
        await message.answer("Бундай тадқиқот мавжуд эмас. Тадқиқот номини текширинг.")
        return

    plate = researches[research_name]
    plate_text = display_plate_as_table(plate)
    file_path = generate_pdf(plate_text)
    await state.clear()
    try:
        with open(file_path, "rb") as pdf_file:
            await message.answer_document(pdf_file, caption=f"Тадқиқот плашкаси '{research_name}'")
    except Exception as e:
        await message.answer("PDFга юклашда хатолик мавжуд. Яна бир уриниб куринг.")

async def main():
    async with bot:
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
