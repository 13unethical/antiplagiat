"""
Наполнение корпуса тестовыми документами на русском и узбекском языках.

Запуск:
    cd backend
    source .venv/bin/activate
    python corpus_seed.py
"""
from __future__ import annotations

import hashlib
import sys
import uuid

# Добавляем путь к приложению
sys.path.insert(0, ".")

SAMPLE_DOCS = [
    {
        "title": "Информатика — основные понятия",
        "language": "ru",
        "source_type": "wiki",
        "url": None,
        "content": """
Информатика — наука о методах и процессах сбора, хранения, обработки, передачи, анализа
и оценки информации с применением компьютерных технологий, обеспечивающих возможность
её использования для принятия решений.

Информатика охватывает алгоритмические процессы, искусственный интеллект, компьютерное
программирование, языки программирования и теорию вычислений. Она занимается как
теоретическими основами, так и практическим применением в области вычислительной техники.

Основными разделами информатики являются теория алгоритмов, теория информации,
теория программирования, теория баз данных, компьютерная графика, искусственный интеллект
и многие другие области.

Алгоритм — это конечная последовательность чётко определённых инструкций для решения
задачи или категории задач. Алгоритмы всегда однозначны и используются как спецификации
для выполнения вычислений.
        """.strip(),
    },
    {
        "title": "Математический анализ — введение",
        "language": "ru",
        "source_type": "wiki",
        "url": None,
        "content": """
Математический анализ — раздел математики, включающий в себя дифференциальное и интегральное
исчисление функций вещественного переменного. Математический анализ тесно связан с геометрией,
алгеброй и другими разделами математики.

Основными понятиями математического анализа являются предел, непрерывность, производная
и интеграл. Эти понятия позволяют исследовать поведение функций, находить скорости изменения
и площади фигур.

Дифференциальное исчисление изучает производную функции и её приложения. Производная
характеризует скорость изменения функции в каждой точке. Геометрически производная
есть угловой коэффициент касательной к графику функции.

Интегральное исчисление является другой важной частью математического анализа и позволяет
вычислять площади криволинейных фигур, объёмы тел вращения и решать дифференциальные уравнения.
        """.strip(),
    },
    {
        "title": "Fizika — mexanika asoslari",
        "language": "uz-Latn",
        "source_type": "wiki",
        "url": None,
        "content": """
Mexanika — fizikaning jismlar harakati va ularni harakatga keltiruvchi kuchlarni o'rganuvchi
bo'limidir. Mexanika klassik mexanika va kvant mexanikasiga bo'linadi.

Klassik mexanika Nyuton qonunlari asosida qurilgan bo'lib, katta jismlarning sekin harakatlarini
tasvirlaydi. Nyutonning birinchi qonuniga ko'ra, tashqi kuch ta'sir etmasa, jism tinch
holatda yoki tekis chiziqli harakat qiladi.

Nyutonning ikkinchi qonuni kuch bilan tezlanish o'rtasidagi bog'liqlikni belgilaydi: kuch
massa va tezlanishning ko'paytmasiga tengdir. Bu qonun mexanikaning asosiy formulasi
hisoblanadi va barcha hisob-kitoblarning negizini tashkil etadi.

Energiya saqlanish qonuni tabiatning universal qonunlaridan biri hisoblanadi. Bu qonunga
ko'ra, yopiq sistemada to'liq mexanik energiya o'zgarmaydi, ya'ni kinetik va potentsial
energiyalarning yig'indisi doimiy bo'lib qoladi.
        """.strip(),
    },
    {
        "title": "Иммануил Кант — философия",
        "language": "ru",
        "source_type": "wiki",
        "url": None,
        "content": """
Иммануил Кант — немецкий философ, один из центральных мыслителей эпохи Просвещения.
Его философские работы оказали огромное влияние на развитие западной мысли и заложили
основы для многих последующих философских школ.

Критическая философия Канта, изложенная в «Критике чистого разума», пытается установить
границы познания и выяснить, что может быть познано с помощью разума, а что выходит
за его пределы. Кант утверждал, что пространство и время не являются свойствами вещей
самих по себе, а представляют собой формы нашего восприятия.

Этика Канта основана на понятии категорического императива: поступай только согласно
тому правилу, следуя которому ты в то же время можешь пожелать, чтобы оно стало
всеобщим законом.
        """.strip(),
    },
    {
        "title": "Биология — строение клетки",
        "language": "ru",
        "source_type": "wiki",
        "url": None,
        "content": """
Клетка — структурная и функциональная единица всех живых организмов. Клетки способны
к самостоятельному существованию, самовоспроизведению и развитию.

Клеточная теория, сформулированная в XIX веке, утверждает, что все живые организмы
состоят из клеток, клетка является основной единицей жизни, и все клетки возникают
из уже существующих клеток путём деления.

Эукариотическая клетка содержит ядро и мембранные органеллы, включая митохондрии,
эндоплазматический ретикулум, аппарат Гольджи и лизосомы. Ядро содержит генетическую
информацию в форме ДНК, организованной в хромосомы.

Прокариотические клетки, в отличие от эукариотических, не имеют оформленного ядра.
Генетический материал прокариот находится прямо в цитоплазме в виде нуклеоида.
        """.strip(),
    },
    {
        "title": "Tarix — O'rta Osiyo sivilizatsiyasi",
        "language": "uz-Latn",
        "source_type": "wiki",
        "url": None,
        "content": """
O'rta Osiyo sivilizatsiyasi juda qadimiy va boy tarixga ega. Bu mintaqada ilk shaharlar
miloddan avvalgi IV-III ming yilliklarda paydo bo'lgan. Zarafshon va Amudaryo vohalarida
qadimiy qishloq xo'jaligi madaniyatlari rivojlangan.

Buyuk Ipak yo'li O'rta Osiyo orqali o'tib, Sharq va G'arbni bog'lagan. Bu yo'l nafaqat
savdo-sotiq uchun, balki madaniyat va bilimlar almashinuvi uchun ham muhim bo'lgan.

Samarqand va Buxoro o'rta asrlarda yirik madaniy va ilmiy markazlarga aylangan. Bu
shaharlarda ko'plab allomalar, shoir va olimlar yashab ijod qilgan. Al-Xorazmiy,
Ibn Sino, Al-Beruniy kabi buyuk olimlar o'z asarlarini shu hududlarda yaratgan.

Temuriylar davrida O'rta Osiyo yana bir marta madaniyat va san'atning gullab-yashnagan
davriga kirdi. Samarqand imperiya poytaxtiga aylandi va ajoyib me'moriy yodgorliklar
barpo etildi.
        """.strip(),
    },
    {
        "title": "Экономика — основы рыночной системы",
        "language": "ru",
        "source_type": "wiki",
        "url": None,
        "content": """
Рыночная экономика — экономическая система, основанная на свободном предпринимательстве,
частной собственности и конкуренции. В рыночной экономике решения о производстве и
потреблении принимаются множеством независимых субъектов.

Спрос и предложение являются основными механизмами рыночной экономики. Закон спроса
гласит, что при прочих равных условиях увеличение цены приводит к снижению спроса.
Закон предложения утверждает, что при росте цены производители готовы предлагать
больше товаров.

Конкуренция — движущая сила рыночной экономики. Она стимулирует производителей
снижать издержки, улучшать качество продукции и внедрять инновации. Монополия,
напротив, ограничивает конкуренцию и может привести к неэффективному распределению
ресурсов.

Деньги выполняют функции средства обращения, меры стоимости и средства накопления.
Денежная система каждой страны регулируется центральным банком, который проводит
денежно-кредитную политику.
        """.strip(),
    },
    {
        "title": "Химия — периодическая таблица элементов",
        "language": "ru",
        "source_type": "wiki",
        "url": None,
        "content": """
Периодическая таблица химических элементов — табличное отображение химических элементов,
упорядоченных по возрастанию атомного номера. Таблица была создана Дмитрием Менделеевым
в 1869 году и стала одним из величайших достижений химии.

Элементы расположены в таблице по периодам (горизонтальные ряды) и группам (вертикальные
столбцы). Элементы одной группы имеют схожие химические свойства, так как имеют
одинаковое число электронов на внешнем энергетическом уровне.

Металлы составляют большинство химических элементов. Они обладают характерными
свойствами: металлическим блеском, электрической проводимостью, ковкостью и тягучестью.
Неметаллы расположены в правом верхнем углу периодической таблицы.

Химическая связь — силы, удерживающие атомы вместе в молекулах и кристаллах.
Основными типами химической связи являются ионная, ковалентная и металлическая.
        """.strip(),
    },
]


def main():
    import hashlib
    import uuid

    # Импортируем сервис корпуса
    from app.services.corpus import ensure_index, index_document, get_document_count

    print("Проверка/создание OpenSearch индекса...")
    if not ensure_index():
        print("WARN: OpenSearch недоступен — документы будут добавлены только в PostgreSQL")
    else:
        print("OK: индекс готов")

    # Добавляем документы напрямую в OpenSearch (без PostgreSQL для seed)
    added = 0
    skipped = 0

    for doc_data in SAMPLE_DOCS:
        content = doc_data["content"]
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, content[:100]))

        ok = index_document(
            doc_id=doc_id,
            title=doc_data["title"],
            content=content,
            url=doc_data.get("url"),
            language=doc_data["language"],
            source_type=doc_data["source_type"],
        )
        if ok:
            added += 1
            print(f"  + {doc_data['title']}")
        else:
            skipped += 1
            print(f"  - {doc_data['title']} (пропущено — OpenSearch недоступен)")

    total = get_document_count()
    print(f"\nГотово: добавлено {added}, пропущено {skipped}")
    print(f"Итого документов в OpenSearch: {total}")


if __name__ == "__main__":
    main()
