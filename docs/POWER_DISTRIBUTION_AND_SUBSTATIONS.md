# Factorio 2.0 Power Distribution & Substation Architecture ⚡
## Space Age Quality Reach, Boundary Mathematics & Zero-Gap Screen Coverage

[**English**](#-english) | [**Türkçe**](#-türkçe)

---

# 🇬🇧 English

This document provides a comprehensive engineering analysis of power distribution across large-scale Factorio displays, covering substation (`substation`) footprint mathematics, Space Age quality scaling, automated copper wiring meshes, boundary geometry, and sandbox deployment modes.

---

## 1. Overview & Core Philosophy

Powering video monitors and ROM memory banks containing tens or hundreds of thousands of active circuit entities presents unique geometric challenges. 

In Factorio, lamps (`small-lamp`) and circuit combinators require continuous electrical power to function. If a substation is cut off or power fluctuates, pixels immediately go dark and clock synchronization is lost. The power distribution engine is designed to satisfy three core principles:
1. **Zero-Gap Visual Integrity:** Displays must maintain 100% continuous lamp matrices without unsightly black holes caused by embedded power poles.
2. **Deterministic Full Coverage:** Every lamp, decoder, ROM combinator, and clock entity must be reliably powered, regardless of aspect ratio or display dimensions.
3. **Automated Construction:** Blueprints pasted by players in-game must be fully self-powering with all copper power connections automatically strung by construction robots.

---

## 2. Engineering Challenges

### 2.1. Visual Integrity (Zero Gaps)
- Substations occupy a physical **2x2 tile** footprint, whereas display lamps occupy **1x1 tile**.
- Indiscriminately dropping substations inside the active screen area would erase 4 pixels per substation, disrupting image presentation.
- The engine places screen-powering substations along perimeter service corridors ($x = -2, y = -2$) and around ROM banks, using the extended supply area to energize the screen from the outside without breaking pixel density.

### 2.2. Boundary Coverage on Arbitrary Resolutions
- Monitors frequently use non-standard resolutions derived from video aspect ratios (e.g. $65 \times 48$, $85 \times 60$, or $105 \times 60$).
- Because display widths and heights are rarely exact multiples of substation grid steps ($18, 20, 22, 24, 28$), simple modular tiling leaves boundary pixels on the right and bottom edges unpowered.
- The boundary algorithm computes exact bounding boxes and dynamically steps outward until all perimeter pixels fall safely inside the supply radius.

### 2.3. Automated 2D Copper Mesh Wiring
- Players pasting complex blueprints must never be forced to manually connect copper wires across hundreds of substations.
- The generator creates a fully interconnected 2D mesh, automatically joining each substation to its horizontal and vertical neighbors via `POLE_COPPER` connections.

---

## 3. Space Age Substation Qualities & Supply Geometry

A substation's bounding box is **2x2 tiles**. When placed with top-left coordinate $(tx, ty)$, its Factorio entity center coordinate is $(tx + 1.0, ty + 1.0)$.

Factorio Space Age introduces 5 quality tiers that expand both supply area and copper wire reach:

| Quality Tier | Quality ID | Supply Area | Wire Reach | Recommended Grid Step | Supply Area (Tiles²) | Relative Gain |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Normal / Common** | `normal` | **18 x 18 tiles** | 18.0 tiles | 18 tiles | 324 tiles² | Baseline (1.0x) |
| **Uncommon** | `uncommon` | **20 x 20 tiles** | 20.0 tiles | 20 tiles | 400 tiles² | +23% (1.23x) |
| **Rare** | `rare` | **22 x 22 tiles** | 22.0 tiles | 22 tiles | 484 tiles² | +49% (1.49x) |
| **Epic** | `epic` | **24 x 24 tiles** | 24.0 tiles | 24 tiles | 576 tiles² | +78% (1.78x) |
| **Legendary** | `legendary` | **28 x 28 tiles** | 28.0 tiles | 28 tiles | 784 tiles² | **+142% (2.42x)** |

> [!TIP]
> **Legendary Quality Efficiency:** Upgrading to Legendary substations increases supply area from $18\times 18$ to $28\times 28$ tiles. This reduces total substation count on massive screens by up to **58%**, drastically decreasing factory area and combinator collision points.

---

## 4. Grid Stepping & Boundary Expansion Mathematics

### 4.1. Anchor Grid Origin $(-2, -2)$
The top-left corner of the display matrix is located at $(0, 0)$ to $(W, H)$. 
By anchoring the primary substation grid at:
$$x_{start} = -2, \quad y_{start} = -2$$
the top-left substation occupies the tile rectangle $[-2, 0) \times [-2, 0)$. This snaps the substation immediately adjacent to the upper-left corner of the display without overwriting pixel $(0, 0)$.

### 4.2. Global Bounding Box & Expansion Loops
The grid stepping algorithm first estimates the maximum horizontal and vertical bounding coordinates, factoring in display dimensions, ROM lane count, and curled layout spans:

$$\text{CombSpan} = \text{cols} \times 4.0 + \left(\frac{\text{cols} \times 4.0}{\text{step}}\right) \times 2.0 + 30.0$$

The grid generator steps outwards in both negative and positive directions:

1. **Negative Direction Loop:**
   ```python
   x_start_g = -2
   while x_start_g > min_x_sub:
       x_start_g -= step
   ```
2. **Positive Direction Loop:**
   ```python
   x_coords = []
   cx = x_start_g
   while cx - half_reach <= max_x_sub:
       x_coords.append(cx)
       cx += step
   ```
   *(where $\text{HalfReach} = \lfloor \text{step} / 2 \rfloor$)*

3. **Substation Coordinate List:**
   $$\text{SubstationsList} = \{ (tx, ty) \mid tx \in x_{coords}, \ ty \in y_{coords} \}$$

### 4.3. Lamp-Substation Collision Masking
If a substation overlaps the active display matrix in embedded layout modes, the engine masks off those exact four tiles:
$$\text{OccupiedLampTiles} = \{ (px, py) \mid px \in [tx, tx+1], \ py \in [ty, ty+1], \ 0 \le px < W, \ 0 \le py < H \}$$
Lamps are never placed at these coordinates, preventing entity collision errors during blueprint import.

---

## 5. Deployment Modes

### 5.1. Behind-the-Screen / Perimeter Mode (Default)
In this mode, the display area `(0..W-1, 0..H-1)` consists of **100% continuous lamps** with zero holes. Substations are positioned along external perimeter corridors ($x = -2, y = -2$), utilizing their supply reach to energize lamps from the edges.

### 5.2. Dual Anchor Substation Standard `(-1, -1)` & `(-1, -3)`
To guarantee modular slicing stability across multi-part blueprints, each slice incorporates fixed alignment substations:
1. **Primary Anchor `(-1.0, -1.0)`:**
   - Functions as the universal registration landmark across all slices ($P_1, P_2, \dots, P_{16}$).
   - Ensures parts snap together in Factorio with zero pixel or combinator drift.
2. **Secondary Anchor `(-1.0, -3.0)`:**
   - Linked to Anchor 1 via copper wire (`POLE_COPPER`) and circuit wire (`WIRE_RED`).
3. **Master Clock Bridge:**
   - The central selector clock (`clock_out_id`) connects via red wire directly to Anchor 1.
   - Anchor 1 distributes `signal-F` along the perimeter lamp bus without crossing active video pixels.

### 5.3. No-Substation Sandbox Mode (`substation_quality = "none"`)
For sandbox gameplay, creative worlds, or modded setups utilizing electric floor tiles:
- The generator removes all substations from the blueprint, reducing entity counts and blueprint size.
- A single small power pole remains at coordinate `(-1, -1)` solely as an alignment registration anchor for multi-part blueprints.

---

## 6. Power Mesh Wiring Architecture

```mermaid
graph TD
    subgraph PowerGrid["Automated 2D Substation Power Mesh"]
        S_00["Substation (-2, -2)"] ---|Copper Wire| S_10["Substation (16, -2)"]
        S_00 ---|Copper Wire| S_01["Substation (-2, 16)"]
        S_10 ---|Copper Wire| S_11["Substation (16, 16)"]
        S_01 ---|Copper Wire| S_11
    end

    subgraph AnchorGroup["Alignment & Clock Bridge"]
        ANC1["Primary Anchor (-1, -1)"] ---|Copper Wire| ANC2["Secondary Anchor (-1, -3)"]
        ANC1 ---|Red Wire: Clock Bridge| ANC2
        CLK["Master Clock (signal-F)"] -->|Red Wire| ANC1
    end

    ANC1 -.->|Copper Auto-Bridge (d <= reach)| S_00
    ANC1 -->|Red Wire Bus| BORDER_LAMPS["Perimeter Screen Lamps"]
    S_00 -.->|Supply Radius| MONITOR["Active Screen Lamps & ROM Banks"]
```

---
---

# 🇹🇷 Türkçe

Bu doküman; Factorio'da video dönüştürücü tarafından oluşturulan devasa lamba/monitör ekranlarının ve ROM bellek bankalarının nasıl enerjilendirildiğini, trafoların (`substation`) yerleşim geometrisini, Space Age kalite kademelerini, otomatik 2B bakır kablo örgüsünü ve yaratıcı (sandbox) modlarını detaylı bir mühendislik perspektifiyle açıklar.

---

## 1. Genel Bakış ve Temel Felsefe

On binlerce veya yüz binlerce devre elemanından oluşan video ekranlarının ve ROM bankalarının kararlı çalışabilmesi için kesintisiz elektrik dağıtımı şarttır. 

Factorio'da lambalar (`small-lamp`) ve devre kombinatörleri çalışmak için sürekli elektrik gücüne ihtiyaç duyar. Bir trafonun bağlantısı kesilirse veya güç dalgalanması yaşanırsa pikseller anında kararır ve saat senkronizasyonu bozulur. Güç dağıtım motoru üç temel ilkeye göre inşa edilmiştir:
1. **Sıfır Boşluklu Görsel Bütünlük:** Ekran yüzeyinde elektrik direklerinin neden olduğu siyah delikler veya piksel boşlukları kesinlikle bulunmamalıdır.
2. **Deterministik Tam Kapsama:** Monitörün en-boy oranı veya boyutu ne olursa olsun her lamba, dekoder, ROM kombinatörü ve saat devresi eksiksiz enerjilendirilmelidir.
3. **Otomatik İnşaat Kolaylığı:** Oyuncular blueprint'i haritaya bastığında inşaat robotları tüm bakır elektrik kablolarını otomatik örmeli; oyuncunun elle hiçbir kablo çekmesine gerek kalmamalıdır.

---

## 2. Mühendislik Zorlukları

### 2.1. Görsel Bütünlük (Sıfır Boşluk)
- Trafolar haritada **2x2 karo** yer kaplarken, monitör lambaları **1x1 karo** alana oturur.
- Ekran matrisinin içine rastgele trafo yerleştirmek, trafo başına 4 pikselin yok olmasına ve ekranda belirgin siyah deliklerin oluşmasına yol açar.
- Motor; ekranı besleyen trafoları çevre servis koridorlarına ($x = -2, y = -2$) ve ROM bankalarının etrafına yerleştirerek, pikselleri dışarıdan besler ve ekranın %100 kesintisiz lamba olarak kalmasını sağlar.

### 2.2. Serbest Çözünürlüklerde Kenar Kapsaması
- Monitörler videonun orijinal en-boy oranına göre hesaplandığı için standart dışı boyutlar sıkça oluşur (örn. $65 \times 48$, $85 \times 60$ veya $105 \times 60$).
- Ekran genişliği ve yüksekliği nadiren trafo adımının ($18, 20, 22, 24, 28$) tam katı olduğundan, basit blok kopyalama ekranın sağ ve alt kenarındaki pikselleri elektriksiz bırakır.
- Sınır algoritması, monitör ve ROM alanlarının dış sınırlarını dinamik olarak hesaplar ve tüm kenar pikseller trafo kapsama alanına girene kadar dışa doğru ek trafo sıraları örer.

### 2.3. Otomatik 2B Bakır Ağ Kablolaması
- Yüzlerce trafodan oluşan devasa bir sistemde oyuncuların trafoları tek tek bakır kabloyla birbirine bağlaması pratik değildir.
- Blueprint derleyicisi, her trafoyu sağındaki ve altındaki komşusuna `POLE_COPPER` bağlantısı ile otomatik bağlayarak tam bir 2B güç ızgarası üretir.

---

## 3. Space Age Trafo Kalite Kademeleri ve Kapsama Geometrisi

Bir trafonun ayak izi **2x2 karo**dur. Sol üst köşesi $(tx, ty)$ koordinatına yerleştirildiğinde, Factorio motorundaki merkez koordinatı $(tx + 1.0, ty + 1.0)$ olur.

Factorio Space Age eklentisi, trafoların hem kapsama alanını hem de bakır kablo erişim menzilini artıran 5 kalite kademesi sunar:

| Kalite Kademesi | Kalite Tanımlayıcısı | Kapsama Alanı | Kablo Menzili | Önerilen Izgara Adımı | Kapsama Alanı (Karo²) | Bağıl Artış |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Normal / Standart** | `normal` | **18 x 18 karo** | 18.0 karo | 18 karo | 324 karo² | Referans (1.0x) |
| **Uncommon (Sıradışı)**| `uncommon` | **20 x 20 karo** | 20.0 karo | 20 karo | 400 karo² | +%23 (1.23x) |
| **Rare (Nadir)** | `rare` | **22 x 22 karo** | 22.0 karo | 22 karo | 484 karo² | +%49 (1.49x) |
| **Epic (Epik)** | `epic` | **24 x 24 karo** | 24.0 karo | 24 karo | 576 karo² | +%78 (1.78x) |
| **Legendary (Efsanevi)**| `legendary` | **28 x 28 karo** | 28.0 karo | 28 karo | 784 karo² | **+%142 (2.42x)** |

> [!TIP]
> **Efsanevi (Legendary) Kalite Avantajı:** Legendary trafolar kapsama alanını $18\times 18$'den $28\times 28$ karoya çıkarır. Bu sayede devasa ekranlarda ihtiyaç duyulan toplam trafo sayısı **%58'e kadar azalır**, fabrika alanı küçülür ve kombinatörlerle çakışma riski en aza iner.

---

## 4. Izgara Adımı ve Sınır Genişletme Matematiği

### 4.1. Çapa Izgara Başlangıcı $(-2, -2)$
Ekran matrisinin sol üst köşesi $(0, 0)$ ile $(W, H)$ aralığındadır.
Ana trafo ızgarasının başlangıç noktası:
$$x_{start} = -2, \quad y_{start} = -2$$
olarak seçilir. Böylece en sol üstteki trafo $[-2, 0) \times [-2, 0)$ karo aralığını kaplar; $(0, 0)$ pikselinin üzerine basmadan ekranın hemen köşesine tam sıfır boşlukla yapışır.

### 4.2. Küresel Sınır Kutusu ve Genişleme Döngüleri
Izgara algoritması ekran boyutlarını, ROM satır sayısını ve kıvrımlı hat genişliklerini hesaba katarak kapsanması gereken en uç koordinatları belirler:

$$\text{CombSpan} = \text{cols} \times 4.0 + \left(\frac{\text{cols} \times 4.0}{\text{step}}\right) \times 2.0 + 30.0$$

Izgara oluşturucu hem negatif hem de pozitif yönde dinamik adımlarla ilerler:

1. **Negatif Yön Döngüsü (Sol/Üst Sınır):**
   ```python
   x_start_g = -2
   while x_start_g > min_x_sub:
       x_start_g -= step
   ```
2. **Pozitif Yön Döngüsü (Sağ/Alt Sınır):**
   ```python
   x_coords = []
   cx = x_start_g
   while cx - half_reach <= max_x_sub:
       x_coords.append(cx)
       cx += step
   ```
   *(Burada $\text{HalfReach} = \lfloor \text{step} / 2 \rfloor$)*

3. **Trafo Koordinat Kümesi:**
   $$\text{SubstationsList} = \{ (tx, ty) \mid tx \in x_{coords}, \ ty \in y_{coords} \}$$

### 4.3. Lamba-Trafo Çakışma Maskelemesi
Trafoların ekranın aktif yüzeyine denk geldiği gömülü modlarda motor, bu 4 karoyu maskeleyerek lamba yerleşiminden hariç tutar:
$$\text{OccupiedLampTiles} = \{ (px, py) \mid px \in [tx, tx+1], \ py \in [ty, ty+1], \ 0 \le px < W, \ 0 \le py < H \}$$
Bu koordinatlarda lamba oluşturulmaz; böylece Factorio'da blueprint basılırken varlık çakışma (collision) hataları engellenir.

---

## 5. Dağıtım ve Yerleşim Modları

### 5.1. Ekran Arkası / Çevre Koridor Modu (Varsayılan)
Bu modda ekran alanı `(0..W-1, 0..H-1)` **%100 kesintisiz lambalardan** oluşur ve sıfır delik içerir. Trafolar dış çevre koridorlarına ($x = -2, y = -2$) yerleştirilerek, geniş besleme yarıçapları ile ekran piksellerini dışarıdan besler.

### 5.2. Çift Çapa Trafosu Standardı `(-1, -1)` ve `(-1, -3)`
Çok parçalı (modular sliced) blueprint'lerin oyunda üst üste kayma olmadan kilitlenebilmesi için her parçada sabit çapa trafoları bulunur:
1. **Birincil Çapa `(-1.0, -1.0)`:**
   - Tüm parçalar ($P_1, P_2, \dots, P_{16}$) arasında evrensel kilitlenme noktasıdır.
   - Parçaların oyunda sıfır piksel veya kombinatör kayması ile birbirine oturmasını sağlar.
2. **İkincil Çapa `(-1.0, -3.0)`:**
   - Birincil çapaya bakır güç kablosu (`POLE_COPPER`) ve devre kablosu (`WIRE_RED`) ile bağlıdır.
3. **Merkezi Saat Köprüsü (Master Clock Bridge):**
   - Merkezi saat devresinin çıkışı (`clock_out_id`) kırmızı kablo ile doğrudan Birincil Çapaya bağlanır.
   - Birincil çapa, `signal-F` saat sinyalini aktif video piksellerini bölmeden ekranın kenar lamba hattı üzerinden tüm sisteme dağıtır.

### 5.3. Trafosuz Sandbox Modu (`substation_quality = "none"`)
Yaratıcı haritalar, sandbox dünyaları veya zemin elektriği modları için:
- Blueprint üzerindeki tüm trafolar kaldırılır; varlık sayısı ve blueprint string boyutu en aza iner.
- Çok parçalı blueprint'lerin birbirine kilitlenebilmesi için `(-1, -1)` koordinatında yalnızca küçük bir elektrik direği bırakılır.

---

## 6. Güç Ağı Kablolama Mimarisi

```mermaid
graph TD
    subgraph PowerGrid["Otomatik 2B Trafo Güç Ağı"]
        S_00["Trafo (-2, -2)"] ---|Bakır Kablo| S_10["Trafo (16, -2)"]
        S_00 ---|Bakır Kablo| S_01["Trafo (-2, 16)"]
        S_10 ---|Bakır Kablo| S_11["Trafo (16, 16)"]
        S_01 ---|Bakır Kablo| S_11
    end

    subgraph AnchorGroup["Hizalama ve Saat Köprüsü"]
        ANC1["Birincil Çapa (-1, -1)"] ---|Bakır Kablo| ANC2["İkincil Çapa (-1, -3)"]
        ANC1 ---|Kırmızı Kablo: Saat Köprüsü| ANC2
        CLK["Merkezi Saat (signal-F)"] -->|Kırmızı Kablo| ANC1
    end

    ANC1 -.->|Otomatik Bakır Bağlantı (d <= menzil)| S_00
    ANC1 -->|Kırmızı Kablo Veri Yolu| BORDER_LAMPS["Kenar Ekran Lambaları"]
    S_00 -.->|Kapsama Yarıçapı| MONITOR["Aktif Ekran Lambaları ve ROM Bankaları"]
```
