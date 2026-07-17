"""
AfriMine AI — Mineral Database
Complete mineral class definitions for Kenya's mining sector.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MineralClass:
    """Single mineral class with metadata."""
    id: int
    name: str
    formula: str
    category: str  # precious | base | industrial | gemstone | rare_earth
    typical_grade_unit: str  # g/t | % | ppm
    color_range: list  # typical colors for visual ID
    kenya_regions: list  # counties where found
    economic_value: str  # high | medium | low
    description: str = ""


MINERAL_CLASSES: list[MineralClass] = [
    MineralClass(0, "gold", "Au", "precious", "g/t",
                 ["gold", "yellow", "metallic"],
                 ["Migori", "Kisumu", "Homa Bay", "Kakamega", "Siaya"],
                 "high", "Primary precious metal, found as nuggets, flakes, or in quartz veins"),
    MineralClass(1, "copper", "Cu", "base", "%",
                 ["copper", "red", "green patina"],
                 ["Kwale", "Kitui", "Machakos"],
                 "high", "Base metal used in electronics and construction"),
    MineralClass(2, "pyrite", "FeS2", "industrial", "%",
                 ["brass yellow", "metallic", "cubic crystals"],
                 ["Narok", "Kajiado", "Nakuru"],
                 "low", "Iron sulfide, 'fool's gold', indicator mineral for gold exploration"),
    MineralClass(3, "quartz", "SiO2", "industrial", "%",
                 ["white", "clear", "purple", "smoky"],
                 ["Taita Taveta", "Machakos", "Kajiado"],
                 "low", "Silicon dioxide, host rock for gold veins, industrial silica source"),
    MineralClass(4, "titanium", "TiO2", "industrial", "%",
                 ["black", "dark brown", "metallic"],
                 ["Kwale", "Kilifi", "Lamu"],
                 "high", "Heavy mineral sands, ilmenite and rutile forms"),
    MineralClass(5, "sodalite", "Na8Al6Si6O24Cl2", "gemstone", "%",
                 ["blue", "white", "grey"],
                 ["Taita Taveta", "Kwale"],
                 "medium", "Blue tectosilicate mineral, decorative stone"),
    MineralClass(6, "ruby", "Al2O3:Cr", "gemstone", "ct",
                 ["red", "pink red", "dark red"],
                 ["Taita Taveta", "Kwale", "Garba Tula"],
                 "high", "Chromium-corundum, precious gemstone"),
    MineralClass(7, "sapphire", "Al2O3:Fe,Ti", "gemstone", "ct",
                 ["blue", "yellow", "pink", "white"],
                 ["Taita Taveta", "Kwale"],
                 "high", "Iron/titanium-corundum, precious gemstone"),
    MineralClass(8, "graphite", "C", "industrial", "%",
                 ["black", "dark grey", "metallic"],
                 ["Kwale", "Taita Taveta", "Kilifi"],
                 "medium", "Carbon allotrope, lubricant and battery anode material"),
    MineralClass(9, "fluorite", "CaF2", "industrial", "%",
                 ["purple", "green", "blue", "clear"],
                 ["Kerio Valley", "Baringo", "West Pokot"],
                 "medium", "Calcium fluoride, flux in steel and aluminium production"),
    MineralClass(10, "bauxite", "Al2O3·2H2O", "industrial", "%",
                 ["brown", "red", "yellow"],
                 ["Kwale", "Kitui"],
                 "medium", "Primary ore of aluminium"),
    MineralClass(11, "manganese", "MnO2", "base", "%",
                 ["black", "dark brown", "grey"],
                 ["Kwale", "Kilifi", "Taita Taveta"],
                 "medium", "Essential alloying element for steel production"),
    MineralClass(12, "limestone", "CaCO3", "industrial", "%",
                 ["white", "grey", "beige"],
                 ["Athi River", "Bamburi", "Homa Bay"],
                 "low", "Calcium carbonate, cement and construction material"),
    MineralClass(13, "diatomite", "SiO2·nH2O", "industrial", "%",
                 ["white", "cream", "light grey"],
                 ["Kariandusi", "Nakuru"],
                 "low", "Fossilized diatoms, filtration and insulation material"),
    MineralClass(14, "soda_ash", "Na2CO3", "industrial", "%",
                 ["white", "colourless"],
                 ["Lake Magadi", "Nakuru"],
                 "medium", "Sodium carbonate, glass and detergent manufacturing"),
    MineralClass(15, "garnet", "Fe3Al2(SiO4)3", "gemstone", "ct",
                 ["red", "brown", "orange", "green"],
                 ["Taita Taveta", "Kwale"],
                 "medium", "Silicate gemstone, also used as abrasive"),
    MineralClass(16, "tourmaline", "Complex borosilicate", "gemstone", "ct",
                 ["green", "blue", "pink", "black"],
                 ["Taita Taveta"],
                 "medium", "Piezoelectric gemstone with wide color range"),
    MineralClass(17, "vermiculite", "Mg,Fe,Al)3(Al,Si)4O10(OH)2·4H2O", "industrial", "%",
                 ["gold", "brown", "silver"],
                 ["Kerio Valley"],
                 "low", "Hydrated phyllosilicate, insulation and horticulture"),
    MineralClass(18, "niobium", "Nb", "rare_earth", "ppm",
                 ["black", "dark grey", "brownish"],
                 ["Kwale"],
                 "high", "Rare metal for superalloys and superconductors"),
    MineralClass(19, "thorium", "Th", "rare_earth", "ppm",
                 ["black", "dark brown"],
                 ["Kwale", "Kilifi"],
                 "high", "Radioactive rare earth, monazite sands"),
]

MINERAL_MAP = {m.id: m for m in MINERAL_CLASSES}
MINERAL_NAME_TO_ID = {m.name: m.id for m in MINERAL_CLASSES}


def get_mineral_by_name(name: str) -> Optional[MineralClass]:
    """Lookup mineral by name (case-insensitive)."""
    return MINERAL_NAME_TO_ID.get(name.lower())


def get_mineral_by_id(class_id: int) -> Optional[MineralClass]:
    """Lookup mineral by class ID."""
    return MINERAL_MAP.get(class_id)
