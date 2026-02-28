"""Enums and value objects used across the domain."""
from enum import Enum


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"


class Ethnicity(str, Enum):
    BLACK = "black"
    WHITE = "white"
    ASIAN = "asian"


class BackendLanguage(str, Enum):
    JAVA = "Java"
    PYTHON = "Python"
    C = "C"
    CPP = "C++"
    CSHARP = "C#"
    DOTNET = ".NET"
    RUBY = "Ruby"
    RUST = "Rust"
    GO = "Go"


class CareerStage(str, Enum):
    INTERN = "Intern"
    JUNIOR = "Junior"
    MID = "Mid"
    SENIOR = "Senior"
    STAFF = "Staff"
    PRINCIPAL = "Principal"
    DISTINGUISHED = "Distinguished"

    @staticmethod
    def progression_order() -> list:
        return [
            CareerStage.INTERN,
            CareerStage.JUNIOR,
            CareerStage.MID,
            CareerStage.SENIOR,
            CareerStage.STAFF,
            CareerStage.PRINCIPAL,
            CareerStage.DISTINGUISHED,
        ]

    def next_stage(self) -> "CareerStage | None":
        order = CareerStage.progression_order()
        idx = order.index(self)
        if idx + 1 < len(order):
            return order[idx + 1]
        return None

    def stage_index(self) -> int:
        return CareerStage.progression_order().index(self)


class ChallengeCategory(str, Enum):
    LOGIC = "logic"
    DOMAIN_MODELING = "domain_modeling"
    ARCHITECTURE = "architecture"
    DISTRIBUTED_SYSTEMS = "distributed_systems"


class MapRegion(str, Enum):
    XEROX_PARC = "Xerox PARC"
    APPLE_GARAGE = "Apple Garage"
    MICROSOFT = "Microsoft"
    NUBANK = "Nubank"
    DISNEY = "Disney"
    GOOGLE = "Google"
    FACEBOOK = "Facebook"
    IBM = "IBM"
    AMAZON = "Amazon"
    MERCADO_LIVRE = "Mercado Livre"
    JP_MORGAN = "JP Morgan"
    PAYPAL = "PayPal"
    NETFLIX = "Netflix"
    SPACEX = "SpaceX"
    TESLA = "Tesla"
    ITAU = "Itau"
    UBER = "Uber"
    NVIDIA = "Nvidia"
    AURORA_LABS = "Aurora Labs"
    NEXUS_LABS = "Nexus Labs"
    SANTANDER = "Santander"
    BRADESCO = "Bradesco"
    GEMINI = "Gemini"
    BIO_CODE_TECHNOLOGY = "Bio Code Technology"
    CLOUD_VALLEY = "Cloud Valley"
    OPENAI = "OpenAI"
    CLAUDE = "Claude"


class GameEnding(str, Enum):
    COMPLETED = "completed"
    GAME_OVER = "game_over"
    IN_PROGRESS = "in_progress"
