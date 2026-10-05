"""Lecture du format DFI : une ligne, puis l'appariement des paires.

Le format va par paires positionnelles — une ligne de type 1 porte les
parcelles meres, la suivante de type 2 les filles — et l'ETL en fait le
produit cartesien. Cet appariement est le point fragile du module : il se
fonde sur l'ordre des lignes, donc il derape sans bruit.
"""

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DfiParsingMixin:
    """Extraction des filiations depuis un fichier DFI."""

    def parse_dfi_line(self, line: str) -> dict | None:
        """Parse a single DFI line according to fixed format.

        Format: dept;commune;prefixe;id_dfi;nature;date;geometre;placeholder;lot;type;parcelles...
        Note: geometre field may contain spaces/newlines, placeholder is "XNUMX"

        Args:
            line: Raw line from DFI file

        Returns:
            Parsed dict or None if invalid
        """
        # Skip empty lines or lines with only whitespace
        if not line.strip():
            return None

        parts = line.split(";")

        # Need at least 10 fields (up to type field)
        if len(parts) < 10:
            logger.warning(f"Invalid DFI line (too few fields: {len(parts)}): {line[:80]}")
            return None

        try:
            # Parse date (format: YYYYMMDD)
            date_str = parts[5].strip()
            if len(date_str) == 8:
                date_validation = datetime.strptime(date_str, "%Y%m%d").date()
            else:
                logger.warning(f"Invalid date format: {date_str}")
                return None

            # Field 7 is placeholder "XNUMX", field 8 is real lot number
            numero_lot = parts[8].strip()

            # Field 9 is type (1 or 2)
            type_ligne = parts[9].strip()

            # Extract parcels (from field 10 onwards, max 175 cells)
            parcelles = []
            for p in parts[10:]:
                p_clean = p.strip()
                # Valid parcel: 2-6 chars (section + number, ex: "AC0026" or "A1200")
                if p_clean and 2 <= len(p_clean) <= 6:
                    parcelles.append(p_clean)

            return {
                "code_departement": parts[0].strip(),
                "code_commune": parts[1].strip(),
                "prefixe": parts[2].strip(),
                "id_dfi": parts[3].strip(),
                "nature_dfi": parts[4].strip(),
                "date_validation": date_validation,
                "numero_lot": numero_lot,
                "type_ligne": type_ligne,
                "parcelles": parcelles,
            }
        except Exception as e:
            logger.error(f"Error parsing DFI line: {e}, line: {line[:80]}")
            return None

    def process_dfi_file(self, file_path: Path) -> list[dict]:
        """Process a complete DFI file into mother-daughter relationships.

        DFI files have paired lines:
        - Line type 1: mother parcels
        - Line type 2: daughter parcels

        We create a cartesian product: each mother × each daughter.

        Args:
            file_path: Path to DFI TXT file

        Returns:
            List of filiation records
        """
        logger.info(f"Processing DFI file: {file_path}")

        filiations = []
        buffer = []

        with open(file_path, encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue

                parsed = self.parse_dfi_line(line)
                if not parsed:
                    continue

                buffer.append(parsed)

                # Process paired lines (type 1 + type 2)
                if len(buffer) == 2:
                    line1, line2 = buffer

                    # Validate it's a proper pair
                    if (
                        line1["id_dfi"] == line2["id_dfi"]
                        and line1["numero_lot"] == line2["numero_lot"]
                    ):
                        # Determine which is mothers and which is daughters
                        if line1["type_ligne"] == "1" and line2["type_ligne"] == "2":
                            mothers = line1["parcelles"]
                            daughters = line2["parcelles"]
                        elif line1["type_ligne"] == "2" and line2["type_ligne"] == "1":
                            mothers = line2["parcelles"]
                            daughters = line1["parcelles"]
                        else:
                            logger.warning(f"Invalid pair types: {line1['type_ligne']}, {line2['type_ligne']}")
                            buffer = []
                            continue

                        # Cartesian product: mothers × daughters
                        for mother in mothers:
                            for daughter in daughters:
                                filiations.append({
                                    "code_departement": line1["code_departement"],
                                    "code_commune": line1["code_commune"],
                                    "prefixe": line1["prefixe"],
                                    "id_dfi": line1["id_dfi"],
                                    "nature_dfi": line1["nature_dfi"],
                                    "date_validation": line1["date_validation"],
                                    "numero_lot": line1["numero_lot"],
                                    "parcelle_mere": mother,
                                    "parcelle_fille": daughter,
                                })
                    else:
                        logger.warning(f"Mismatched pair at line {line_num}")

                    buffer = []

        logger.info(f"Extracted {len(filiations)} filiation relationships")
        return filiations
