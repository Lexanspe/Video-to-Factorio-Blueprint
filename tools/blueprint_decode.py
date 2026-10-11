import base64
import json
import zlib


def encode_blueprint(data: dict) -> str:
    raw_json = json.dumps(data, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw_json, level=9)
    return "0" + base64.b64encode(compressed).decode("utf-8")


def decode_blueprint(bp_string: str) -> dict:
    bp_string = bp_string.strip()
    if not bp_string.startswith("0"):
        raise ValueError("Geçersiz blueprint: Başında '0' versiyon baytı yok.")
    compressed_bytes = base64.b64decode(bp_string[1:])
    raw_json = zlib.decompress(compressed_bytes).decode("utf-8")
    return json.loads(raw_json)


if __name__ == "__main__":
    # 1. Örnek geçerli bir veri oluşturup encode ediyoruz:
    orijinal_veri = {
        "blueprint": {
            "item": "blueprint",
            "label": "Test Direk",
            "entities": [
                {
                    "entity_number": 1,
                    "name": "small-electric-pole",
                    "position": {"x": 0.5, "y": 0.5},
                }
            ],
            "version": 281479271743488,
        }
    }

    bp_string = encode_blueprint(orijinal_veri)
    print("Oluşturulan Blueprint String:\n", bp_string)

    # 2. Şimdi bunu decode ediyoruz:
    cozulen_veri = decode_blueprint(bp_string)
    print("\nBaşarıyla Decode Edilen JSON:\n", json.dumps(cozulen_veri, indent=2))