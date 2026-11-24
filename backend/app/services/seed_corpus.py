"""
Стартовый корпус для антиплагиата (без Docker).

Содержит несколько эталонных академических текстов на русском и узбекском.
При старте приложения, если корпус пуст, документы сохраняются в Postgres,
загружаются в кэш шинглов и индексируются в Qdrant (семантика).
"""
from __future__ import annotations

import hashlib
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.corpus import CorpusDocument

logger = logging.getLogger(__name__)

# (title, language, url, content)
STARTER_DOCS: list[tuple[str, str, str, str]] = [
    (
        "МСФО для малого и среднего бизнеса: обзор",
        "ru",
        "https://example.org/ifrs-sme-overview",
        "Малый и средний бизнес является основой экономики большинства стран. "
        "Чтобы оставаться на плаву, компаниям нужны не только деньги, но и точная "
        "информация о своём финансовом состоянии. Международные стандарты финансовой "
        "отчётности для малых и средних предприятий были разработаны для того, чтобы "
        "упростить учёт и снизить издержки на подготовку отчётности. Эти стандарты "
        "убирают сложные требования, которые редко применяются в небольших компаниях, "
        "и делают отчётность более понятной для банков и инвесторов. Переход на "
        "международные стандарты требует подготовки кадров, времени и ресурсов. "
        "В развивающихся странах принятие новых правил не означает, что отдельные "
        "фирмы будут применять их правильно на практике.",
    ),
    (
        "Внедрение МСФО в Узбекистане",
        "ru",
        "https://example.org/ifrs-uzbekistan",
        "В Узбекистане улучшение финансовой отчётности является приоритетом по мере "
        "модернизации экономики. Крупные и общественно значимые компании постепенно "
        "переходят на полные международные стандарты. Однако для малого и среднего "
        "бизнеса сохраняются национальные правила учёта. Основными барьерами внедрения "
        "выступают нехватка квалифицированных бухгалтеров, ограниченные бюджеты, "
        "устаревшие компьютерные системы и слабая методическая поддержка. Многие фирмы "
        "ведут учёт вручную, в тетрадях или простых таблицах. Исследования показывают "
        "разрыв между требованиями закона и реальной практикой ведения учёта на местах.",
    ),
    (
        "Институциональная теория и ресурсный подход",
        "ru",
        "https://example.org/institutional-rbv",
        "Институциональная теория объясняет, как законы, профессиональные привычки и "
        "отраслевые нормы заставляют предприятия менять правила учёта. Ресурсный подход "
        "показывает, почему две компании, сталкиваясь с одними и теми же законами, "
        "получают разные результаты в зависимости от персонала, денег и технологий. "
        "Совместное применение этих теорий позволяет рассматривать проблему как смесь "
        "внешнего давления и внутренней силы компании. Таким образом, готовность фирмы "
        "принять стандарт определяется как внешними институциональными факторами, так и "
        "внутренними ресурсами.",
    ),
    (
        "Искусственный интеллект в образовании",
        "ru",
        "https://example.org/ai-education",
        "Искусственный интеллект постепенно меняет сферу образования. Системы на основе "
        "машинного обучения помогают преподавателям проверять работы, выявлять пробелы "
        "в знаниях и персонализировать обучение. В то же время широкое использование "
        "генеративных моделей ставит вопросы академической честности. Студенты могут "
        "применять инструменты для написания эссе, что усложняет оценку самостоятельности "
        "работы. Поэтому образовательным учреждениям необходимы прозрачные правила "
        "использования таких технологий и инструменты для проверки текстов на машинную "
        "генерацию.",
    ),
    (
        "Kichik va o'rta biznes uchun moliyaviy hisobot",
        "uz-Latn",
        "https://example.org/uz-sme-reporting",
        "Kichik va o'rta biznes ko'pchilik mamlakatlar iqtisodiyotining asosi hisoblanadi. "
        "Kompaniyalar barqaror ishlashi uchun nafaqat mablag', balki o'zining moliyaviy "
        "holati haqida aniq ma'lumotga ham muhtoj. Xalqaro moliyaviy hisobot standartlari "
        "kichik korxonalar uchun hisobni soddalashtirish va hisobot tayyorlash xarajatlarini "
        "kamaytirish maqsadida ishlab chiqilgan. O'zbekistonda bu standartlarni joriy etish "
        "malakali buxgalterlar yetishmasligi va cheklangan byudjet kabi to'siqlarga duch keladi. "
        "Shuni ta'kidlash joizki, qonun qabul qilinishi uning amalda to'g'ri qo'llanilishini "
        "anglatmaydi.",
    ),
    (
        "Цифровая экономика и малый бизнес",
        "ru",
        "https://example.org/digital-economy-sme",
        "Цифровизация открывает новые возможности для малого бизнеса, но требует вложений в "
        "технологии и обучение. Электронный документооборот, онлайн-кассы и облачные сервисы "
        "учёта позволяют снизить издержки и повысить прозрачность. Тем не менее многие "
        "предприниматели не обладают нужными навыками, а стоимость перехода остаётся высокой. "
        "Государственная поддержка и доступные образовательные программы играют важную роль "
        "в адаптации малого бизнеса к условиям цифровой экономики.",
    ),
    (
        "Основы гражданского права",
        "ru",
        "https://example.org/civil-law-basics",
        "Гражданское право регулирует имущественные и связанные с ними личные "
        "неимущественные отношения между участниками оборота. Основными принципами "
        "выступают равенство сторон, неприкосновенность собственности, свобода договора "
        "и недопустимость произвольного вмешательства в частные дела. Договор считается "
        "заключённым, когда стороны достигли согласия по всем существенным условиям в "
        "требуемой форме. Нарушение обязательств влечёт гражданско-правовую ответственность, "
        "как правило в форме возмещения убытков или уплаты неустойки.",
    ),
    (
        "Методы обучения в современной школе",
        "ru",
        "https://example.org/teaching-methods",
        "Современная педагогика смещает акцент с передачи готовых знаний на развитие навыков "
        "самостоятельного мышления. Активные методы обучения, такие как проектная работа, "
        "дискуссии и обучение в сотрудничестве, повышают вовлечённость учащихся. Важную роль "
        "играет формирующее оценивание, которое помогает ученику видеть свой прогресс, а не "
        "только итоговую отметку. Использование цифровых инструментов расширяет доступ к "
        "материалам, но не заменяет роль учителя как организатора учебного процесса.",
    ),
    (
        "Введение в базы данных",
        "ru",
        "https://example.org/databases-intro",
        "База данных представляет собой организованный набор данных, доступ к которым "
        "осуществляется через систему управления базами данных. Реляционная модель "
        "описывает данные в виде таблиц, связанных между собой по ключам. Язык SQL "
        "используется для создания, изменения и выборки данных. Нормализация помогает "
        "устранить избыточность и аномалии при обновлении. Индексы ускоряют поиск, но "
        "замедляют вставку и занимают дополнительное место на диске.",
    ),
    (
        "Основы маркетинга",
        "ru",
        "https://example.org/marketing-basics",
        "Маркетинг — это деятельность по созданию, продвижению и предоставлению ценности "
        "потребителям. Классическая модель включает четыре элемента: продукт, цену, место "
        "и продвижение. Исследование рынка позволяет понять потребности целевой аудитории "
        "и оценить конкурентов. Сегментирование делит рынок на группы со схожими запросами, "
        "а позиционирование формирует образ продукта в сознании потребителя. Цифровые каналы "
        "изменили способы коммуникации с клиентом, усилив роль данных и персонализации.",
    ),
    (
        "Ekologik muammolar va barqaror rivojlanish",
        "uz-Latn",
        "https://example.org/uz-ecology",
        "Zamonaviy dunyoda ekologik muammolar global xarakterga ega. Havo va suvning "
        "ifloslanishi, o'rmonlarning kamayishi va iqlim o'zgarishi inson faoliyati bilan "
        "bevosita bog'liq. Barqaror rivojlanish hozirgi avlod ehtiyojlarini kelajak avlod "
        "imkoniyatlariga zarar yetkazmasdan qondirishni nazarda tutadi. Resurslardan "
        "oqilona foydalanish, qayta ishlash va qayta tiklanadigan energiya manbalariga "
        "o'tish ekologik barqarorlikning asosiy yo'nalishlari hisoblanadi.",
    ),
    (
        "История развития письменности",
        "ru",
        "https://example.org/writing-history",
        "Письменность возникла как способ фиксировать информацию и передавать её во времени "
        "и пространстве. Ранние системы, такие как клинопись и иероглифы, использовали знаки "
        "для обозначения предметов и понятий. Появление алфавита, в котором знаки обозначают "
        "звуки, упростило запись и сделало грамотность доступнее. Распространение бумаги и "
        "книгопечатания многократно ускорило обмен знаниями и повлияло на развитие науки, "
        "образования и культуры.",
    ),
    (
        "Управление проектами: базовые понятия",
        "ru",
        "https://example.org/project-management",
        "Проект — это временное предприятие, направленное на создание уникального продукта "
        "или результата. Управление проектом включает планирование сроков, бюджета и ресурсов, "
        "а также контроль рисков и качества. Жизненный цикл обычно состоит из инициации, "
        "планирования, исполнения, мониторинга и завершения. Чёткое определение целей и "
        "ожиданий заинтересованных сторон снижает вероятность срыва сроков. Гибкие подходы "
        "позволяют адаптировать план по мере поступления обратной связи.",
    ),
]


def _load_dir_docs() -> list[tuple[str, str, str, str]]:
    """Читает .txt/.md из backend/corpus_seed/ как документы корпуса.
    Язык определяется автоматически, заголовок — имя файла."""
    import pathlib
    from app.services.language import detect_language

    base = pathlib.Path(__file__).resolve().parents[2] / "corpus_seed"
    docs: list[tuple[str, str, str, str]] = []
    if not base.is_dir():
        return docs
    for p in sorted(base.glob("**/*")):
        if p.suffix.lower() not in (".txt", ".md") or not p.is_file():
            continue
        try:
            content = p.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if len(content.split()) < 20:
            continue
        try:
            lang = detect_language(content)
        except Exception:
            lang = "ru"
        docs.append((p.stem, lang, f"file://corpus_seed/{p.name}", content))
    return docs


async def seed_and_load(db: AsyncSession) -> None:
    """Наполняет корпус в Postgres (идемпотентно, по content_hash) и загружает кэш шинглов."""
    from app.services import corpus as corpus_service

    candidates = list(STARTER_DOCS) + _load_dir_docs()

    existing = set(
        (await db.execute(select(CorpusDocument.content_hash))).scalars().all()
    )
    added = 0
    for title, lang, url, content in candidates:
        h = hashlib.sha256(content.encode()).hexdigest()
        if h in existing:
            continue
        existing.add(h)
        doc_id = uuid.uuid4()
        db.add(CorpusDocument(
            id=doc_id, title=title, url=url, language=lang,
            source_type="seed", content_hash=h, content=content,
            word_count=len(content.split()), opensearch_id=str(doc_id),
        ))
        added += 1
    if added:
        await db.commit()
        logger.info("Corpus: added %d new document(s)", added)

    rows = (await db.execute(select(CorpusDocument))).scalars().all()
    corpus_service.load_cache(rows)


async def index_semantics() -> None:
    """Индексирует корпус в Qdrant (эмбеддинги). Запускается в фоне — первый раз
    скачивает модель (~0.22 ГБ), поэтому не должен блокировать старт сервера."""
    import asyncio
    from app.database import AsyncSessionLocal
    from app.services import embedder as embedder_service

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(CorpusDocument))).scalars().all()
    for r in rows:
        if not r.content:
            continue
        try:
            await asyncio.to_thread(
                embedder_service.index_corpus_doc,
                str(r.id), r.title, r.content, r.url, r.language,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qdrant index failed (semantic disabled): %s", exc)
            return
    logger.info("Semantic corpus indexing complete (%d docs)", len(rows))
