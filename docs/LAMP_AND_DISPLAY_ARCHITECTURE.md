# Factorio 2.0 Lamp & Display Architecture 📺
## TrueColor Packed RGB, Zero Combinator Clutter & Display Bus Design

[**English**](#-english) | [**Türkçe**](#-türkçe)

---

# 🇬🇧 English

This document explains how digital video frames are converted into a Factorio lamp (`small-lamp`) monitor matrix, covering the Factorio 2.0 (Space Age) lamp architecture, packed color formats, signal filtering, and electrical bus routing.

---

## 1. Overview & Core Philosophy

In legacy Factorio (1.1), lamps were primarily used for illumination or basic indicators switching between 8 discrete virtual color signals (`signal-red`, `signal-green`, etc.).

In this project, every single lamp functions as a **discrete physical monitor pixel**:
- **Dimensions:** **1x1 tile** per pixel.
- **Coordinates:** If a pixel's top-left corner is at `(x, y)`, its physical entity center in Factorio is `(x + 0.5, y + 0.5)`.
- **Operating Mode:** Operates using **Factorio 2.0 Packed RGB (`color_mode: 2`)** without requiring bulky combinator arrays beside the display.

---

## 2. Factorio 1.1 vs Factorio 2.0 (Space Age) Lamp Architecture

| Feature | Legacy Method (Factorio 1.1) | Modern Method (Factorio 2.0 / Space Age) |
| :--- | :--- | :--- |
| **Color Depth** | Only 8 virtual color signals | **16 Million Colors (TrueColor Packed RGB)** |
| **Circuit Footprint** | Constant Combinator + Green Wire per pixel | **Zero combinators on the display surface** |
| **Signal Filtering** | Hardcoded conditional threshold (`signal > 0`) | **`rgb_signal` dedicated channel mapping** |
| **Daytime Visibility**| Lamps turn off automatically during daylight | **`always_on: true` ensures 24/7 continuous playback** |
| **Blueprint Size** | Bulky wiring networks inflate string size | **Extremely lightweight, optimized JSON schema** |

---

## 3. Lamp Entity JSON Schema

In Factorio 2.0, display lamps follow this standardized blueprint structure:

```json
{
  "entity_number": 1,
  "name": "small-lamp",
  "position": {
    "x": 0.5,
    "y": 0.5
  },
  "always_on": true,
  "control_behavior": {
    "use_colors": true,
    "color_mode": 2,
    "rgb_signal": {
      "type": "item",
      "name": "iron-plate",
      "quality": "normal"
    }
  },
  "color": {
    "r": 1.0,
    "g": 1.0,
    "b": 1.0,
    "a": 1.0
  }
}
```

### Parameter Breakdown:
1. **`position` (`{"x": float, "y": float}`)**:
   Defines the physical center of the lamp on the Factorio grid (e.g., pixel `(0, 0)` maps to `(0.5, 0.5)`).
2. **`always_on: true`**:
   Bypasses the daytime sleep cycle so the video plays continuously day and night.
3. **`use_colors: true`**:
   Enables dynamic circuit network color control for the lamp.
4. **`color_mode: 2` (Packed RGB)**:
   Instructs the lamp to decode a single 24-bit integer into full RGB channels:
   $$\text{packed\_rgb} = (R \ll 16) \mid (G \ll 8) \mid B$$
5. **`rgb_signal` (`{"type": str, "name": str, "quality": str}`)**:
   The specific signal filter assigned to this lamp. On a shared green trunk bus carrying thousands of packed signals simultaneously, each lamp filters and reads only the signal matching its assigned `name` and `quality` to display its respective pixel value.
6. **Trunk Bus Routing**:
   Display lamps are daisy-chained with green wire into horizontal or vertical stripes, connecting directly to the stripe decoder output without intermediate logic.

---
---

# 🇹🇷 Türkçe

Bu doküman, dijital bir görselin veya videonun Factorio lambaları (`small-lamp`) kullanılarak oyunda nasıl kusursuz bir ekrana dönüştürüldüğünü, Factorio 2.0 lamba mimarisini, renk kodlama formatını ve sinyal filtreleme kurallarını açıklar.

---

## 1. Genel Bakış ve Temel Felsefe

Klasik Factorio'da lambalar yalnızca gece aydınlatması veya 8 temel sanal renk sinyali arasında geçiş yapan göstergeler olarak kullanılırdı.

Bu projede her bir lamba monitördeki **bağımsız tek bir piksel** gibi davranır:
- **Boyut:** **1x1 karo** (Her piksel 1 Factorio lambasıdır).
- **Konum:** Sol üst köşesi `(x, y)` olan pikselin fiziksel merkez koordinatı `(x + 0.5, y + 0.5)` olur.
- **Çalışma Modu:** Factorio 2.0'ın `color_mode: 2` (Packed RGB) teknolojisiyle lambaların yanında hantal kombinatörlere gerek kalmaksızın çalışır.

---

## 2. Factorio 1.1 ile Factorio 2.0 (Space Age) Karşılaştırması

| Özellik | Eski Yöntem (Factorio 1.1) | Yeni Yöntem (Factorio 2.0 / Space Age) |
| :--- | :--- | :--- |
| **Renk Skalası** | Sadece 8 sanal renk sinyali | **16 Milyon Renk (TrueColor Paketli RGB)** |
| **Devre İhtiyacı** | Piksel başına Sabit Kombinatör + Yeşil Kablo | **Ekran yüzeyinde sıfır kombinatör** |
| **Sinyal Filtresi** | Sabit eşik koşulu (`sinyal > 0`) | **`rgb_signal` ile özel sinyal kanalı eşleme** |
| **Gündüz Görünürlüğü**| Gündüzleri lambalar otomatik sönerdi | **`always_on: true` ile 7/24 kesintisiz oynatma** |
| **Blueprint Boyutu** | Ağır kablolama nedeniyle devasa JSON dökümü | **Son derece hafif ve optimize JSON şeması** |

---

## 3. Lamba Entity JSON Şeması

Factorio 2.0'da bir ekran lambası şu standart blueprint yapısına sahiptir:

```json
{
  "entity_number": 1,
  "name": "small-lamp",
  "position": {
    "x": 0.5,
    "y": 0.5
  },
  "always_on": true,
  "control_behavior": {
    "use_colors": true,
    "color_mode": 2,
    "rgb_signal": {
      "type": "item",
      "name": "iron-plate",
      "quality": "normal"
    }
  },
  "color": {
    "r": 1.0,
    "g": 1.0,
    "b": 1.0,
    "a": 1.0
  }
}
```

### Parametre Açıklamaları:
1. **`position` (`{"x": float, "y": float}`)**:
   Factorio ızgarasında lambanın merkezini belirler (örneğin `(0, 0)` pikseli için merkez `(0.5, 0.5)`'tir).
2. **`always_on: true`**:
   Gündüz uyku döngüsünü devre dışı bırakır; video gece ve gündüz kesintisiz olarak 7/24 oynatılır.
3. **`use_colors: true`**:
   Lambanın renk kontrolünü devre ağına bağlar.
4. **`color_mode: 2` (Packed RGB)**:
   Lambaya gelen 32-bit işaretli tamsayıyı 24-bit RGB bileşenlerine çözmesini söyler:
   $$\text{packed\_rgb} = (R \ll 16) \mid (G \ll 8) \mid B$$
5. **`rgb_signal` (`{"type": str, "name": str, "quality": str}`)**:
   Bu lambaya özel olarak atanmış sinyal filtresidir. Ortak yeşil veri yolu üzerinde aynı anda taşınan binlerce paketli sinyal arasından, her lamba yalnızca kendi adına ve kalitesine eşleşen sinyali dinleyerek doğru piksel rengini görüntüler.
6. **Veri Yolu Kablolaması (Trunk Bus)**:
   Ekrandaki lambalar yatay veya dikey şeritler halinde yeşil kabloyla birbirine zincirleme bağlanır ve doğrudan şerit çıkışına bağlanır; arada hiçbir ek mantık kapısına gerek kalmaz.
