"""
Generates naturally looking text addresses etc..

Original work:
  https://github.com/azist/azos/blob/master/src/Azos/Text/NaturalTextGenerator.cs

Source data is in public domain:
  https://github.com/azist/azos/blob/master/src/Azos/Text/ConanDoyle.txt
  https://github.com/azist/azos/blob/master/src/Azos/Text/JackLondon.txt


Copyright (C) 2011 - 2026 Azist, MIT License
"""

import functools
import importlib.resources
import random

US_STATES: tuple[str, ...] = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA",
    "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR",
    "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
)


DOMAIN_NAMES: tuple[str, ...] = (
    "google.com", "bing.com", "yahoo.com", "facebook.com", "twitter.com", "github.com", "azoslib.io", "orbitz.com",
    "newegg.com", "ebay.com", "amazon.com", "weather.com", "youtube.com", "wikipedia.org", "google.co.in",
    "live.com", "yandex.ru", "linkedin.com", "vk.com", "reddit.com", "msn.com", "wordpress.com", "mail.ru",
    "pinterest.com", "alibaba.com", "google.es", "google.ca", "crailgslist.org", "ok.ru", "google.ru",
    "livejournal.com", "rambler.ru", "lenta.ru", "dropbox.com",
)


TLD_NAMES: tuple[str, ...] = (
    ".com", ".org", ".net", ".edu", ".gov", ".co", ".us", ".mobi", ".me", ".com", ".ru", ".io", ".ca", ".am", ".ar",
    ".au", ".be", ".com", ".by", ".ca", ".com", ".cs", ".de", ".dk", ".es", ".eu", ".fi", ".fr", ".com", ".net",
    ".us", ".org", ".net", ".gr", ".il", ".it", ".jp", ".kr", ".me", ".lv", ".md", ".com", ".no", ".pl", ".tr",
    ".ua", ".uk", ".com", ".net", ".us", ".org", ".ru", ".in", ".co.in",
)


POPULAR_FIRST_NAMES: tuple[str, ...] = (
    "Adam", "Alex", "Sasha", "Alexander", "Noah", "Liam", "Jacob", "Mason", "William", "Ethan", "Michael", "Jayden",
    "Daniel", "Bill", "Mike", "Bob", "Frank", "Ferdinand", "Trevor", "Dmitry", "Ivan", "Nicola", "Yasha", "Mark",
    "Geoff", "Jeff", "John", "Jon", "Ian", "Ilan", "David", "Robert", "Chuck", "Donald", "Richard", "Serge",
    "Victor", "Akhmed", "Amid", "Alec", "Dodik", "Nick", "Freddie", "Fred", "Alfred", "Harry", "Jerry", "Jacob",
    "Gabriel", "Logan", "James", "Jim", "Anthony", "Harish", "Sandeep", "Jose", "Hasan", "Hosen", "Samir", "Sumir",
    "Valery", "Izya", "Moshe", "Abraham", "Rajneesh", "Eric", "Derek", "Gary", "Benjamin", "Samuel", "Ryan",
    "Vincent", "Sean", "Shawn", "Stepan", "Oleg", "Vladimir", "Tolik", "Eugene", "Jeremy", "Don", "Ben", "Farukh",
    "Garik", "Dima", "Denys", "Misha", "Roma", "Roman", "Osyk", "Alik", "Maksym", "Max", "Tobias", "Boris",
    "Charles", "Edward", "Kevin", "Andrew", "Dennis", "Joshua", "Stephen", "Steve", "Larry", "Jesse", "Danny",
    "Luis", "Lukash", "Luke", "Antonio", "Anua", "Dale", "Curtis", "Tony", "Stanley", "Manuel", "Leonard", "Randy", "Carlos",
    "Russell", "Ruben", "Pedro", "Raul", "Leslie", "Cecil", "Chester", "Andre", "Herman", "Vernon", "Ramon", "John",
    "Maurice", "Dustin", "Adelia", "Sophia", "Emma", "Olivia", "Isabella", "Rita", "Rosa", "Raya", "Inga", "Ava",
    "Mila", "Katya", "Helena", "Lina", "Dina", "Dorah", "Debbi", "Elly", "Emily", "Tonya", "Tanya", "Elizabeth",
    "Nastya", "Helga", "Lynda", "Mona", "Ornella", "Antonina", "Lisa", "Ivana", "Odessa", "Mercedes", "Lida",
    "Nadya", "Gabriella", "Linda", "Matilda", "Anthonia", "Betty", "Barbara", "Dorothy", "Sukha", "Feride", "Halida",
    "Karen", "Margaret", "Nancy", "Sarah", "Ann", "Jennifer", "Laura", "Suma", "Sharon", "Otilia", "Patricia",
    "Crystal", "Morra", "Diana", "Theresa", "Sara", "Judy", "Grace", "Janice", "Gloria", "Jacqueline", "Donna",
    "Angela", "Klava", "Nina", "Ella", "Alla", "Evgeniya", "Lena", "Luda", "Ludmila", "Beba", "Basya", "Dinara",
    "Gulnara", "Stella", "Lara", "Larissa", "Irina", "Ivette", "Natasha", "Helen", "Sandra", "Ruth", "Marie", "Diane", "Alice",
    "Julie", "Amy", "Stephanie", "Rebecca", "Carmen", "Hazel", "Amber", "Eva", "April", "Leslie", "Monica", "Ava",
    "June", "Sally", "Sara", "Erica", "Dolores", "Lynn", "Alicia", "Jill", "Erin", "Marina", "Veronica", "Katie", "Alma",
    "Sue", "Beth", "Jeanne", "Pearl", "Maureen", "Colleen", "Joy", "Claudia",
)


POPULAR_LAST_NAMES: tuple[str, ...] = (
    "Smith", "Johnson", "Jackson", "Harris", "Brown", "Jones", "Davis", "Garcia", "Menendez", "Williams", "Miller",
    "Wilson", "Moore", "Taylor", "White", "Black", "Swift", "Martinez", "Anderson", "Lewis", "Fox", "Lee", "Scott",
    "Brown", "Adams", "Stewart", "Morris", "Sanchez", "Baker", "King", "Knight", "Cooper", "Collins", "Murphy",
    "Reed", "Brown", "Cook", "Morgan", "Harris", "Williams", "Rogers", "Evans", "Parker", "Ivanov", "Petrov",
    "Sidorov", "Ross", "Ford", "Hamilton", "Fisher", "Boobermani", "Goldman", "Harris", "Goldberg", "Silberman", "Smith",
    "Silverman", "Smyth", "Yee", "Kennedy", "Twain", "Simpson", "Gagarin", "Gomez", "Williams", "Warren", "Jonson", "Fox", "Cox",
    "Riley", "Cunnigham", "Heart", "Holst", "Gustaveli", "Andrews", "Spencer", "Palmer", "Noel", "Edwards", "Williams", "Bell",
    "Richardson", "Smith", "Perry", "Miller", "Knob", "Cube", "Long", "Alton", "Aberman", "Doberman", "Zoe", "Zoo",
    "Vakyadi", "Chervonolobskiy", "Williams", "Orlovski", "Jonson", "Johnson", "Dovidoff", "Semerenko", "Shilo", "Kravchenko",
    "Terasini", "Echt", "Bonini", "Fortaleza", "Odessa", "Varshavskiy", "Yablonovski", "Tarkovski", "Zigelboim", "Shreddinger",
    "Shreder", "Fat", "Man", "Camastra", "Chelentano", "More", "Mutti", "Lee", "Miller", "Bach", "Calmar", "Price",
    "Dassin", "Dalida", "Sinatra", "Mercury", "Kobzon", "Yasenin", "Shevchenko", "Serov", "Repin", "Chopin",
    "Mozart", "Corleone", "Smith", "Johnson", "Jonson", "Jensen", "Brown", "Popoff", "Popov", "Morgan", "Kelly",
    "Allen", "Cooper", "Moore", "Davis", "Jones", "Swanson", "Smith", "Brown", "Young", "White", "Lee", "Lewis", "Thomas",
    "Adams", "Smith", "Johnson", "Williams", "Neuman", "Einstein", "Abermudani", "Borman", "Beck", "Dancer", "Dog", "Lancer",
    "Prayer", "Goodman", "Hopewell", "McCloud", "McKnight", "Meduza", "Mendoza", "Sikorski", "Petroff", "Vivaldi",
    "Donahue", "Grant", "Grand", "Belosi", "Pelozi", "Zimmer", "Zomer", "Youth", "Truth", "Snakes", "Drake", "Knoll",
    "Von Brown", "Von Neumann", "Van Gog", "Van Degraph", "D'Artatgnian", "Aramis", "Monet", "Solos", "Solon", "Seibertgh",
    "Euclid", "Lomonosov", "Plato", "Platon", "Buch", "Bush", "Groover", "Hoover", "Lincoln", "Toad", "Malcolm",
    "Scriabin", "Babel", "Glenn", "Leonov", "Monroe", "Moonlite", "Lite", "Krishnasamy", "Liteman", "Bloomberg", "Bloome", "Pub",
    "Shrub", "Broad", "Tief", "Kartofel", "Fleisch", "Shmotzer", "Smutsich", "Sieg", "Mag", "Nasser", "Nasarudi",
    "Babadjanyan", "Khachaturyan", "Shostakovich", "Glinka", "Musorgsky", "Prokofiev", "Khazanov", "Catani", "Chopin",
    "Placido", "Leone", "Bulioni", "D'Armoniac", "D'Trevil", "De-Richelieu", "Bordeaux", "Mazarin", "Nazarin", "Mudder",
    "Nazareth", "Goliath", "Pupperman", "Khibibidze", "Viceman", "Wiseman", "Olivie", "Allard", "Baudini", "Adam", "Anua",
    "Beaulieu", "Caron", "De la Fontaine", "Fay", "Fotel", "Czerven", "Abandonato", "Genis", "Gedis", "Adamaitis", "Accardi",
    "Agnelutti", "Tutti", "Maestoso", "Fuocco", "De Vitis", "De Luca", "De Rege", "De Palma", "Castro", "Cuoco",
    "Crespo", "Giacomo", "Colombo", "Barad", "Gorskiy", "Gurali", "Char", "Bassi", "Dada", "Bhalla", "Comar", "Tartik", "Karduk",
    "Tobriz", "Bhattacharyya", "Khurana", "Manda", "Goswami", "Krishnamurthy", "Swaminathan", "Venkatesh", "Babaladze",
    "Surendrakrishnan", "Nebaran", "Moldavan", "Chaimovitsch", "Gutenmacher", "Geshefter", "Kutz", "Allyev", "Zarov",
    "Afonin", "Hera", "Ira", "Filipov", "Smith", "Brown", "Jackson", "Johnson", "Adams", "Davis", "Palmer", "Gernicherniutis",
    "Williams", "Miller", "Kozlov", "Fyodorov", "Maximova", "Orloff", "Orlov", "Yakovlev", "Perry", "Miller", "Khmalishvily",
    "Heart", "Goodman", "Goodwill", "Holyman", "Long", "Fox", "Smith", "Williams", "Brown", "Romanov", "McLoud", "Zaba"
)


CITY_SUFFIXES: tuple[str, ...] = (
    "berg", "burg", "ville", "will", " Village", "dorf", " Dorf", "grad", "stan", "ovo", " Park", "town", " Town",
    "cker", " Ridge", " Heights", " Valley", " Hall", " Hill", "mento", " Bay", "wood", " Forest", " Woods",
    " Creek", " College", " Falls", " Pines", " Hills", "lin", "lyn", "ton", " Port", " Lake", "field", " Field",
    "view", " View", " Pond", " Ranch", " Beach", " Palace", " Lodge", " Gorge", " Glen", " Barney", " Cove",
    " La Mar", " Au Prince", " Moon Bay", " of Prussia", " Lake City", " Gul Nest", " Gul Cove", " Air", " Mount",
    " Harbor", " Coast", " Heaven", " Den", "slav", "ino", "tino", " Point", " Grove", " Grove City", " Valley View",
    " Harbor View", " Hills City", " Station",
)


STREET_SUFFIXES: tuple[str, ...] = (
    " way", " Way", " blvrd.", " Boulevard", " ave", " ave.", " Avenue", " avenue", " wy.", " rd", " Court",
    " court", " Way", " trail", " Trail", " rd.", " road", " Road", " Circle",
)


POPULAR_CITY_NAMES: tuple[str, ...] = (
    "New York", "Washington", "Philadelphia", "Cleveland", "Hudson", "Canoga Park", "Los Angeles", "Chester",
    "Bristol", "Moscow", "Odessa", "Kiev", "Marion", "Boise", "Franklin", "Greenville", "Mayfield", "Clinton",
    "Sodom", "Salem", "Fairview", "Madison", "Arnold", "Stow", "Dallas", "Ashland", "London", "Paris", "Oxford",
    "Oxnard", "Arlington", "Jackson", "Burlington", "Toronto", "Manchester", "Chita", "Milton", "Centerville",
    "Clayton", "Dayton", "Troy", "Lexington", "Milford", "Dover", "Newport", "Samara", "Bugaz", "Haifa", "Hopewell",
    "Phoenix", "San Diego", "Austin", "Indianapolis", "Athens", "Angola", "San Antonio", "Nordonia", "Macedinia",
    "North Royalton", "Seattle", "Denver", "Boston", "Nashville", "Brighton", "Albuquerque", "Omaha", "Oakland",
    "Raleigh", "Belgorod", "Belgrade", "Sofia", "Sevastopol", "Khersones", "Miami", "Atlanta", "Baltimore", "Tucson",
    "Newark", "Henderson", "Lincoln", "Greensboro", "Toledo", "Winston-Salem", "Chesapeake", "Richmond",
    "Chattanooga", "Choochoo",
)


LAST_NAME_SUFFIXES: tuple[str, ...] = (
    "ani", "any", "ana", "anha", "an", "avich", "asta", "astra", "astro", "ala", "ada", "adi", "acht", "ams", "by",
    "bo", "bi", "bin", "bina", "ban", "ben", "bore", "beck", "back", "backer", "burger", "berg", "bala", "butler",
    "brook", "bridge", "boim", "boym", "cle", "cli", "chevy", "ckin", "ckino", "ckina", "cori", "ckori", "cory",
    "ckory", "chuk", "chook", "choo", "chu", "chuh", "chi", "chev", "cheva", "dze", "dom", "dara", "dori", "dero",
    "der", "dorah", "elsk", "er", "et", "eta", "ema", "etski", "etsky", "ech", "echt", "enser", "fi", "fy", "fina",
    "fyna", "fe", "field", "feld", "gomery", "grey", "gray", "grim", "grihm", "gay", "gai", "gi", "gy", "go", "ga",
    "ge", "hi", "hy", "ini", "iny", "in", "ina", "im", "itz", "its", "itsik", "itsyk", "jer", "jo", "joo", "jen",
    "kin", "kino", "kina", "komo", "kori", "kari", "khmali", "khmer", "lar", "ler", "logo", "led", "lida", "lidah",
    "lume", "luma", "ledge", "lidge", "man", "mas", "mana", "mark", "menko", "menka", "medov", "medova", "metov",
    "metova", "mali", "malykh", "nog", "nam", "ni", "nay", "nenko", "nenka", "nov", "nova", "nero", "nemo", "ovich",
    "ovytch", "ov", "ova", "off", "offa", "overy", "owery", "omery", "omely", "orra", "ora", "orah", "on", "po",
    "pa", "pu", "per", "puma", "quen", "queen", "qwin", "rin", "rina", "rima", "riy", "riya", "ridge", "rosen",
    "smith", "ser", "shvili", "shvily", "shkin", "shkina", "soh", "sa", "so", "shevitsch", "schevich", "solo",
    "sanov", "sanova", "sanoff", "sanoffa", "spen", "spenser", "tov", "tova", "tkin", "tkina", "tkyn", "tkyna",
    "timer", "tymer", "tzeh", "tze", "ter", "xi", "xoo", "yn", "yelsk", "yan", "yana", "yala", "vi", "vy", "vir",
    "vira", "war", "wer", "wor", "work", "werk", "wis", "ung", "undig", "una", "uno", "uni", "uma", "umah", "zer",
    "zo", "za", "zehr", "zola", "zolah", "zanov", "zanova",
)


# Module-private generator seeded from OS entropy at startup, isolated from the global random state
_rnd = random.Random()

_MIN_INT = -(2**31)
_MAX_INT = 2**31 - 1
_POSITIVE_MASK = 0x7FFFFFFF


def seed(value: int | None = None) -> None:
    """
    Re-seeds the generator. Pass an int for reproducible output (e.g. in tests),
    or None to re-seed from OS entropy
    """
    _rnd.seed(value)


def generate(length: int = 150) -> str:
    """
    Generates human-readable English text of up to the specified length which is 10 chars at minimum.
    If zero (or less) is passed then generates a message of random length
    """
    if length <= 0:
        length = 15 + __rndi_range(0, 135)
    if length < 10:
        length = 10

    text = __get_random_text_source()
    i = __scroll_to_word_start(text, __rndi_range(0, len(text) - 1))

    result: list[str] = []
    skipping = False
    length_after_last_word = 0
    while True:
        if i >= len(text):
            i = __scroll_to_word_start(text, 0)
        chr_ = text[i]
        i += 1

        if not __filter(chr_):
            if len(result) >= length:
                break
            if not skipping:
                length_after_last_word = len(result)
            skipping = True
            continue

        if skipping:
            result.append(" ")
        skipping = False
        result.append(chr_)

    if len(result) > length:
        del result[length_after_last_word:]

    return "".join(result)


def generate_word(min_length: int = 4, max_length: int = 20) -> str:
    """
    Generates a random English word which is of the specified size. The min size must be at least 4 chars
    """
    if min_length < 4:
        min_length = 4
    if max_length < min_length:
        max_length = max(20, min_length)

    text = __get_random_text_source()
    i = __scroll_to_word_start(text, __rndi_range(0, len(text) - 1))

    while True:
        word: list[str] = []
        while True:
            if i >= len(text):
                i = __scroll_to_word_start(text, 0)
            chr_ = text[i]
            i += 1

            if not __filter(chr_):
                break
            word.append(chr_)

        if min_length <= len(word) <= max_length:
            return "".join(word)


def generate_first_name() -> str:
    """Generates a string that resembles a human first name"""
    rnd = __rndi()

    if rnd > -1500000000:
        return POPULAR_FIRST_NAMES[(_POSITIVE_MASK & rnd) % len(POPULAR_FIRST_NAMES)]

    prefix = LAST_NAME_SUFFIXES[(_POSITIVE_MASK & __rndi()) % len(LAST_NAME_SUFFIXES)]
    suffix = LAST_NAME_SUFFIXES[(_POSITIVE_MASK & rnd) % len(LAST_NAME_SUFFIXES)]

    return __capitalize(prefix) + suffix


def generate_last_name() -> str:
    """Generates a string that resembles a human last name"""
    rnd = __rndi()

    if 0 < rnd < 123000000:
        return POPULAR_LAST_NAMES[(_POSITIVE_MASK & rnd) % len(POPULAR_LAST_NAMES)]

    short = rnd > 1543000000

    if short:
        prefix = LAST_NAME_SUFFIXES[(_POSITIVE_MASK & __rndi()) % len(LAST_NAME_SUFFIXES)]
    else:
        while True:
            prefix = generate_word(4, 8)
            if "'" not in prefix:
                break
        prefix = prefix.lower()

    suffix = LAST_NAME_SUFFIXES[(_POSITIVE_MASK & rnd) % len(LAST_NAME_SUFFIXES)]

    if not short and rnd < -1543000000:
        prefix, suffix = suffix, prefix

    return __capitalize(prefix) + suffix


def generate_city_name() -> str:
    """Generates a string that resembles a city name"""
    rnd = __rndi()

    if rnd < -1750000000:
        return POPULAR_CITY_NAMES[(_POSITIVE_MASK & rnd) % len(POPULAR_CITY_NAMES)]

    if rnd > 0:
        prefix = POPULAR_FIRST_NAMES[(_POSITIVE_MASK & __rndi()) % len(POPULAR_FIRST_NAMES)]
    else:
        prefix = POPULAR_LAST_NAMES[(_POSITIVE_MASK & __rndi()) % len(POPULAR_LAST_NAMES)]

    suffix = CITY_SUFFIXES[(_POSITIVE_MASK & rnd) % len(CITY_SUFFIXES)]

    return __capitalize(prefix) + suffix


def generate_us_city_state_zip() -> str:
    """
    Generates a string that resembles a city/state/zip in a US address.
    The states/zips are NOT consistent
    """
    state = US_STATES[(_POSITIVE_MASK & __rndi()) % len(US_STATES)]
    zip_code = __rndi_range(0, 99999)
    return f"{generate_city_name()}, {state} {zip_code:05d}"


def generate_address_line() -> str:
    """Generates a string that resembles an address line"""
    street_number = __rndi_range(1, 10000)

    rnd = __rndi()

    if rnd % 3 == 0:
        street = generate_first_name()
    elif rnd % 2 == 0:
        street = generate_last_name()
    else:
        street = generate_city_name()

    if rnd > 0:
        street += STREET_SUFFIXES[(_POSITIVE_MASK & __rndi()) % len(STREET_SUFFIXES)]

    rnd2 = __rndi()

    # C# % truncates toward zero, so only the magnitude matters for the Math.Abs(rnd2 % n) cases
    if rnd2 % 7 == 0:
        street += " apt #" + str(abs(rnd2) % 18) + chr(ord("A") + (rnd2 & 0x8))
    elif rnd2 % 5 == 0:
        street += " apt. " + str(abs(rnd2) % 18) + chr(ord("a") + (rnd2 & 0x8))
    elif rnd2 % 4 == 0:
        street += " suite " + str(abs(rnd2) % 180)
    elif rnd2 % 3 == 0:
        street += " room " + str(abs(rnd2) % 180)

    return f"{street_number} {street}"


def generate_full_name(middle: bool = False) -> str:
    """Generates a string that looks like a human name, optionally with a middle name/initial"""
    fname = generate_first_name()
    lname = generate_last_name()

    if not middle:
        return fname + " " + lname

    rnd = __rndi()

    if rnd > 0:
        if (rnd & 1) == 0:
            mname = chr(ord("A") + (rnd % 25))
        else:
            mname = generate_first_name()

        return fname + " " + mname + " " + lname

    return fname + " " + lname


def generate_email() -> str:
    """Generates a string that looks like an email"""
    rnd = __rndi()

    user = generate_first_name()
    if rnd % 5 == 0:
        user += "." + generate_last_name()
    if rnd % 7 == 0:
        user += str(1900 + abs(rnd) % 115)

    if rnd < -1500000000:
        domain = DOMAIN_NAMES[(_POSITIVE_MASK & __rndi()) % len(DOMAIN_NAMES)]
    elif rnd % 3 == 0 and len(user) < 11:
        domain = generate_word() + "." + generate_city_name() + TLD_NAMES[(_POSITIVE_MASK & __rndi()) % len(TLD_NAMES)]
    else:
        domain = generate_word(8) + TLD_NAMES[(_POSITIVE_MASK & __rndi()) % len(TLD_NAMES)]

    rnd2 = __rndi()

    if len(user) < 5 and rnd2 % 17 != 0:
        user += str(abs(rnd) % 99)

    if rnd2 < 1700000000:
        user = user.lower()

    return (user + "@" + domain.lower()).replace("'", ".").replace(" ", ".")


@functools.cache
def __load_text(name: str) -> str:
    ref = importlib.resources.files(__package__).joinpath("content", name)
    return ref.read_text(encoding="utf-8-sig")


def __get_random_text_source() -> str:
    return __load_text("JackLondon.txt" if __rndi() > 0 else "ConanDoyle.txt")


def __scroll_to_word_start(text: str, i: int) -> int:
    n = len(text)
    while text[i] not in " .,?!\r\n":
        i += 1
        if i == n:
            i = 0

    while not text[i].isalnum():
        i += 1
        if i == n:
            i = 0

    return i


def __filter(chr_: str) -> bool:
    return chr_ == "'" or chr_ == "-" or chr_.isalnum()


def __capitalize(s: str) -> str:
    return s[0].upper() + s[1:].lower()


def __rndi() -> int:
    """Random signed 32-bit integer"""
    return _rnd.randint(_MIN_INT, _MAX_INT)


def __rndi_range(b1: int, b2: int) -> int:
    """Random integer in the inclusive range"""
    return _rnd.randint(b1, b2)
