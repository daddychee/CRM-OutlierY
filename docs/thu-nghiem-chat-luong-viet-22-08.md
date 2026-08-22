# Thử nghiệm chất lượng viết — Content Ultimate

**Ngày 22/08/2026 · người dựng: Bot · cần feedback của team Vận hành**

Từ 07/08 team gần như ngừng dùng công cụ vì **"viết không tốt"**. Chúng tôi đã đi tìm nguyên
nhân bằng cách đo trên chính những bản đã viết, tìm ra **hai nguyên nhân kỹ thuật**, sửa cả
hai, rồi viết lại **cùng một kịch bản Uzbekistan** để so.

Tài liệu này có: (1) hai nguyên nhân và đã sửa gì, (2) số đo trước/sau, (3) **toàn văn 5
chương của cả hai bản** để mọi người đọc, (4) mấy câu hỏi mong team trả lời.

> **Điều kiện so sánh giữ y hệt**: cùng outline, cùng model `glm-5.2`, cùng hồ sơ giọng
> A014 Amazing. Chỉ khác đúng hai thay đổi dưới đây.

---

## 1. Hai thay đổi về logic

### Thay đổi 1 — Bản hướng dẫn cho AI tự nó đầy dấu gạch ngang dài

Trong bản viết của AI có rất nhiều dấu `—` (gạch ngang dài). Văn người viết gần như **không
bao giờ** dùng dấu này: đo trên toàn bộ corpus của các tác giả trong kho ra **0,00–1,30 lần
trên 1.000 từ**, trong khi bản AI viết ra **13–17 lần**. Đây là dấu vân tay dễ nhận ra nhất
của văn máy.

Ban đầu tưởng do luật chưa đủ chặt, vì trong bản hướng dẫn đã có câu *"mỗi đoạn nhiều nhất
một dấu gạch ngang dài"*. Nhưng đo lại thì AI **không hề tuân luật đó**: 26–59% số đoạn có
từ 2 dấu trở lên. Siết chặt câu chữ sẽ vô ích.

Nguyên nhân thật nằm chỗ khác: **chính bản hướng dẫn viết đầy dấu gạch ngang dài**. Khối
luật đo ra **28,6 dấu trên 1.000 từ**, cả bản hướng dẫn là 11,2 — trong khi bản AI viết ra
13–17. Nói cách khác, AI **bắt chước cách viết của tài liệu dạy nó**, chứ không nghe câu ra
lệnh trong đó.

**Đã sửa**: gỡ sạch dấu gạch ngang dài khỏi 25 câu trong bản hướng dẫn, thay bằng dấu hai
chấm hoặc dấu phẩy. **Không đổi một từ nào** — đã kiểm bằng cách so từng chữ trước và sau.

### Thay đổi 2 — "Neo giọng" quá mỏng và chọn sai chỗ

Để AI viết đúng giọng một tác giả, công cụ đưa vào vài **đoạn văn mẫu** của tác giả đó làm
mốc. Trước đây chỉ đưa **3 đoạn, khoảng 200–330 từ** — quá ít so với cả trăm dòng luật trong
cùng bản hướng dẫn. Đây chính là lý do văn hay bị **vụn, đọc như liệt kê**.

Đo kỹ còn thấy vấn đề thứ hai, nặng hơn: **3 đoạn mẫu đó chọn lệch**, không đại diện cho
giọng thật:

| tác giả | 3 đoạn mẫu cũ | văn thật của họ |
|---|---|---|
| Derek Muller | 33,3% câu dài | **9,3%** |
| Tribes | 26,7% câu dài | **15,0%** |
| Carl Sagan | 30,2 từ/câu · 0% câu ngắn | **18,0 từ/câu · 21,4% câu ngắn** |

Tức AI đang được chỉ vào một cái đích **không phải nhịp văn thật** của tác giả.

**Đã sửa**: viết một bộ chọn mẫu mới. Nó đọc toàn bộ kho văn của tác giả, cắt thành từng
khối, rồi chọn ra khoảng **1.840 từ** sao cho **nhịp của tập mẫu khớp với nhịp văn thật**
(số từ mỗi câu, tỉ lệ câu ngắn, tỉ lệ câu dài). Đo trên cả 12 hồ sơ trong kho: **12/12 đều
khớp hơn hẳn** so với 3 đoạn cũ.

Bộ chọn này cũng **tự loại file phụ đề thô** (loại văn bản chép lời nói, không có dấu chấm
phẩy). Nhờ đó phát hiện thêm: ba hồ sơ lâu nay bị coi là hỏng (Ventures, Discovery Ventures,
Discover Ventures) thực ra **có 3/5 file văn tốt**, chỉ 2 file là phụ đề thô — và đúng 2 file
đó lại là chỗ 3 đoạn mẫu cũ được lấy ra. Ba hồ sơ này **không hỏng, chỉ bị lấy sai chỗ**.

### Những gì KHÔNG đổi

Công thức viết chương, cách chia độ sâu, độ dài mục tiêu, cấu trúc outline, cách viết hook —
**giữ nguyên hoàn toàn**. Hai thay đổi trên chỉ chạm vào *dấu câu trong bản hướng dẫn* và
*đoạn văn mẫu đưa cho AI*.

---

## 2. Số đo

Đo trên 5 chương đầu của cả hai bản (khoảng 1.550 từ mỗi bản), cùng một outline.

| Chỉ số | Bản CŨ | Bản MỚI | Văn người (đích) |
|---|---|---|---|
| Dấu gạch ngang dài / 1.000 từ | 18,04 | **9,80** (giảm 46%) | 0,04 |
| Câu cụt (dưới 8 từ) | 45,9% | **37,5%** (giảm 8,4 điểm) | 29,5% |
| Số từ mỗi câu | 11,7 | **12,8** | 13,2 |
| Độ lệch nhịp so với văn thật | 0,93 | **0,44** (giảm 53%) | 0 |
| Bám giọng (7 chỉ số) | 86% | 57% | — |

**Về chỉ số cuối tụt xuống** — nói thẳng chứ không giấu, và nêu đích danh:

| chỉ số | đích | khoảng cho phép | bản CŨ | bản MỚI |
|---|---|---|---|---|
| `punct_freq_total` (mật độ dấu câu) | 0,085 | 0,074–0,096 | 0,085 ✓ | **0,072 ✗** |
| `function_word_freq` (tỉ lệ từ chức năng) | 0,327 | 0,309–0,345 | 0,337 ✓ | **0,364 ✗** |
| `ttr` (độ đa dạng từ vựng) | 0,327 | 0,309–0,344 | 0,432 ✗ | 0,413 ✗ *(mới gần đích hơn)* |
| 4 chỉ số còn lại | | | ✓ | ✓ |

Cả hai chỉ số trượt đều là **hệ quả trực tiếp của câu dài hơn và ít dấu gạch ngang hơn** —
tức đúng hai thứ đợt sửa này nhắm tới. Đáng chú ý nhất: `punct_freq_total` **đếm cả dấu gạch
ngang dài vào mật độ dấu câu**, nên bản sạch dấu gạch ngang bị chấm là "kém giống", dù dấu
gạch ngang chính là dấu vân tay của máy. Chỗ này thước đo sai chứ không phải bản văn sai.

Thêm một điểm về cách chấm: trượt 2/7 chỉ số mà tổng tụt 29 điểm nghĩa là **thang quá thô**
(mỗi chỉ số nặng ~14 điểm, ăn thua ở ngưỡng đóng/mở). Con số tổng % này nên bỏ, chỉ báo cáo
từng chỉ số như bảng trên. Đây cũng là lý do cần team đọc bằng mắt.

**Một điểm còn nợ**: 9,80 dấu gạch ngang/1.000 từ vẫn cao (mức "nặng" là từ 8,0). Truy ra
thì nó **không đến từ đoạn mẫu mới** (đoạn mẫu có đúng 0 dấu), mà đi kèm câu dài — AI dùng
dấu này để nối mệnh đề khi viết câu dài. Sẽ xử ở đợt sau.

---

## 3. Toàn văn hai bản để đọc

Bản cũ là bản **namtn viết ngày 22/08**, bản mới viết lại cùng outline sau khi sửa.

---

## Chương 1

### Bản CŨ

The most populous country in Central Asia has no coastline. Not a single port. Not one harbor. Landlocked — bordered by five neighbors and cut off from every ocean on Earth. The terrain sprawls vast across the continent's heart, a landscape of burning desert and snowcapped mountain. And yet this harsh, sealess expanse holds more people than any country in the region. Since breaking free from the Soviet Union in nineteen ninety-one, Uzbekistan has stood as the demographic center of gravity for all of Central Asia. Not Kazakhstan, which stretches larger by land. Not Turkmenistan, which sits on more gas. Uzbekistan. The one with the people.

At its center: Tashkent. The capital. A city that was never small. For decades under Soviet rule, Tashkent operated as one of the most vital trading hubs in the entire USSR — the node where cotton, silk, and grain moved across the empire in railcars and freight trucks. The Soviets built it into a machine. Boulevards wide enough for tanks. Rail lines fanning out in every direction. A Silk Road city rebuilt as a Soviet engine. And when the empire finally crumbled, the engine stayed running. Still humming. Still the largest city in Central Asia.

Before we go further — where are you watching this from? Drop your country in the comments. I'm always curious who travels this far with me.

But Tashkent's trade and traffic, its people and its boulevards — none of that is what makes Uzbekistan wealthy. The real fortune doesn't move on rails. It sits in the ground. And the scale of it is almost impossible to believe.

### Bản MỚI

Uzbekistan. That is the name most people cannot find on a map. It sits at the very heart of Central Asia, enormous and landlocked, bordered by five nations with not a single coastline to its name. What it has instead is terrain. Vast, unrelenting terrain. The interior is dominated by the Kyzyl Kum, the Red Sand, a desert so large it covers nearly three hundred thousand square kilometers, cracked open by sun and wind and almost empty of life. Then in the east, the land folds upward. The Tien Shan and Pamir mountains rise along the borders, snow-fed and severe, and between those two extremes, the desert floor and the mountain wall, people have been building cities for three thousand years.

Here is what is surprising. Since Uzbekistan gained independence from the Soviet Union in 1991, it has stood as the most populous nation in all of Central Asia. Not Kazakhstan, which is larger on the map. Not Afghanistan, which shares its southern border. Uzbekistan. Roughly thirty-five million people, living in a country that is eighty percent sand.

The capital is Tashkent, which for decades served as one of the great trading hubs of the Soviet empire, where goods from every corner of the union changed hands before moving east.

Before we go any further, where are you watching this from? Drop your country in the comments. I am always curious who travels this far with me.

A country this large, this populous, sitting on this much land, you would expect it to hold real wealth. And it does. But the fortune underneath Uzbekistan is not the kind you can see from the road.

---

## Chương 2

### Bản CŨ

Uzbekistan sits on one of the richest mineral footprints on the planet. Not oil. Not gas. Gold. Uranium. Cotton.

Start with gold. The Muruntau open-pit mine, carved into the Kyzylkum Desert, is the single largest gold mine anywhere on earth. An excavation so vast it shows up on satellite imagery. A pale crater widening year after year in an already pale landscape. Uzbekistan ranks among the top ten gold-producing nations in the world, and Muruntau alone has yielded more than two thousand tons of the metal since the first cut was made. The numbers are difficult to picture. They keep digging.

Then uranium. The country holds the seventh-largest uranium reserves on the planet, and for decades the state mining company has pulled yellowcake from deep beneath those same desert sands. Not shipped abroad as raw ore. Processed on-site, refined, sealed. One of the few nations in the world that manufactures its own nuclear fuel from the ground up.

Cotton they called white gold, and it came at a cost no one counted for decades. Under Soviet central planning, the rivers that fed the Aral Sea were diverted into millions of hectares of irrigation-fed cotton fields. The Aral — once the fourth-largest inland body of water on earth — shrank to a fraction of its former size. Fishing villages stranded miles from any shore. Hulls of ships sitting in the sand like the bones of something that used to live there. Despite having no coastline, despite that dying sea, the country remains economically strong, exporting energy and raw materials the world keeps buying. The ground compensates for what the geography lacks.

But here's the strange part. For all that wealth beneath the surface — the gold, the uranium, the cotton — you don't feel it standing on the street. Not yet. Because long before any of this was pulled from the earth, something else was already here. Something older than the mines, older than the Soviets, older than the desert itself.

### Bản MỚI

It sits below the desert. Below the mountains. In the rock, in the soil, in the long cotton fields that stretch to every horizon.

Uzbekistan is one of the top gold producers on Earth. Not in Central Asia — in the world. The Muruntau mine, carved into the Kyzylkum Desert, is the single largest open-pit gold mine on the planet, and it alone produces more gold each year than most countries manage in a decade. Then there is uranium. The same ground holds deposits that put Uzbekistan among the top ten producers globally, shipping it to nuclear power plants across continents. And cotton — the crop that once clothed the entire Soviet empire still grows here in staggering volume, picked and pressed and sent abroad by the ton.

Then there is the gas. Uzbekistan sits on proven natural gas reserves that rank among the largest in all of Eurasia. Pipelines carry it north to Russia, east across the steppe into China, over mountain ranges that would stop most countries cold. Nearly a fifth of everything the country earns comes from energy. Every winter, it heats homes in cities that have never heard the name Uzbekistan.

Here is what makes this strange. This is a country with no coastline. No port. No sea route to anywhere. And the Aral Sea, once the fourth-largest lake on Earth, has been shrinking for decades, bled dry to irrigate those very cotton fields until what remains is mostly salt, dust, and the skeletons of fishing vessels. You would think a landlocked country watching its own sea disappear would struggle. It has not. The gold, the uranium, the cotton, and a steady flow of natural gas and energy exports hold the whole economy upright.

But the land held power long before anyone dug a mine or planted a field. And what the conquerors left behind is worth more than anything still in the ground.

---

## Chương 3

### Bản CŨ

Trade. For two thousand years, that single word defined everything that moved across this soil. The Silk Road didn't pass through here as an afterthought — it was born here, threaded through cities like Samarkand and Bukhara, weaving east toward China and west toward the Mediterranean. Merchants carried silk, spices, lapis lazuli, and ideas along these routes. The cities along the way grew fat on the exchange. Not just wealthy. Civilizational. Samarkand stood at the crossroads of the known world, and everyone who wanted to control that crossroads came here — Genghis Khan among them, whose horsemen burned the city to the ground in twelve-twenty.

But the man who mattered most was not a conqueror who came to destroy. He came to build. Timur — known to the West as Tamerlane — rose from the Chagatai Khanate in the late fourteenth century, and by thirteen-seventy he had claimed Samarkand as his capital. What he did next separates him from every warlord who ever thundered across this part of the world. He didn't just take the city. He remade it. Timur raided the known world not for gold alone but for its minds — dragging architects from Damascus, astronomers from Persia, mathematicians from India, and poets from every court between here and Anatolia, and depositing all of them in Samarkand. The city became the brightest intellectual furnace of its age. Observatories mapped the stars. Madrasas taught astronomy alongside theology, and the line between the two did not exist. Islamic learning, philosophy, medicine, mathematics — all of it converging on a single Central Asian city at a time when most of Europe was still stumbling through darkness. His grandson Ulugh Beg carried the project forward, building an observatory so advanced that its star catalogue remained unmatched for centuries. The blue domes of the Registan, the massive arch of the Bibi-Khanum Mosque — not ruins of a forgotten empire. The physical proof of a moment when this land was the center of the world.

But that moment didn't last. And what came after — what nearly erased all of this from memory — is the part that makes everything that followed so remarkable.

### Bản MỚI

This was the heart of the Silk Road. Not a stop along the way — the center of it. Every caravan carrying silk from China, every merchant hauling spice and glass from the Mediterranean, every scholar and soldier and pilgrim moving between East and West had to pass through this stretch of Central Asia. Silk. Spice. Paper. Gunpowder. Ideas traveled the same roads as merchants, and merchants traveled the same roads as armies. That position made the land irresistible — and it made it a target. Genghis Khan swept through in the thirteenth century and shattered the cities he found. Others came before and after, each trying to hold the road that held the world together.

But one man came not just to take. He came to build. His name was Timur — the West called him Tamerlane — and in the late fourteenth century he chose Samarkand as the capital of an empire stretching from the edge of China to the borders of Turkey. Timur was brutal. That is not in dispute. But he was also something his legend rarely carries: a builder on a scale Central Asia had never seen. He filled Samarkand with the finest architects, astronomers, mathematicians, and poets he could find — sometimes carrying them back from conquered cities by force. What grew from that was not a military camp. It was a renaissance. Observatories tracked the stars with instruments that would not be matched in Europe for a century. Madrasas taught astronomy, mathematics, and philosophy alongside Islamic theology, and the scholars who passed through them shaped the intellectual life of the entire Islamic world. The courtyards were sheathed in blue tile so precise that craftsmen today still cannot fully reproduce it. Samarkand under Timur was not merely wealthy. It was one of the most learned cities on Earth.

What was built here had to survive centuries of decline, of empire, of being absorbed into someone else's story. The question is whether it would endure that long silence — and what happened when the silence finally broke.

---

## Chương 4

### Bản CŨ

Centuries of decline. That's what came after. The Silk Road emptied as global trade shifted to the sea, and the cities that had connected East to West drifted into long, quiet irrelevance. The Russian Empire arrived in the eighteen-sixties and absorbed the region into its frontier. Then came the Soviets. Seventy years of rule from Moscow. The Uzbek language was pushed aside. The Cyrillic alphabet was stamped onto schoolbooks and street signs. And a civilization's heritage was treated the way occupying powers always treat the culture of the occupied — catalogued, set behind glass, reduced to folklore.

Then, in nineteen ninety-one, the Soviet Union came apart. And on September first of that year, Uzbekistan declared itself a sovereign nation. Not a kingdom. Not an empire. A republic. For the first time in centuries, the people of this land had a country they could call their own.

What followed was not just political independence. It was a cultural awakening. The Uzbek language surged back into public life — into schools, into government, into the ordinary rhythms of the street. The Latin alphabet began replacing Cyrillic, reconnecting the written word to its Turkic roots, undoing one of the most visible marks of Soviet control. Traditional music returned to the squares. Craft guilds that had nearly disappeared began producing the old ceramics, the old silks, the old embroidered cloths. Heritage was no longer something preserved behind museum glass — it was something being lived. And Bukhara and Samarkand stood as proud symbols of a revitalized Central Asian nation, proof that what decline and occupation had tried to erase, independence was bringing back.

Give this a like if you learned something new. And for a country this determined to reclaim its identity — the question is, how hard is it to actually get in? As it turns out, not nearly as hard as you'd think.

### Bản MỚI

The silence broke in 1991.

For centuries, this land had been folded into someone else's story. The great Khanates crumbled. The Russians came, and after them the Soviets, redrawing borders from offices in Moscow, naming republics that had never existed as such before. Cities that once commanded the Silk Road — Samarkand, Bukhara, Khiva — became ornaments in a system that never asked what they wanted to be called.

Not free. Not sovereign. Not their own.

Then the Soviet Union came apart, and in 1991, Uzbekistan stood up as a nation for the first time in modern memory. What followed was not just political. It was personal.

The Uzbek language, which had spent decades being pushed aside for Russian in classrooms, in offices, in the formal machinery of the state, came back into daylight. Parents who had grown up speaking Russian at school and Uzbek only at home watched their children do something they never could — learn, read, and write in the language of their own grandmothers without shame or hesitation. Street signs changed. Television changed. An entire generation began closing a gap that had been kept open by force for seventy years.

And the pride that came with it was not the loud, performative kind that exists to prove a point to outsiders. It was quieter and steadier than that. It showed itself in the restoration of Bukhara's blue domes, scrubbed clean and reinforced so they might last another five centuries. In Samarkand's Registan, polished to glow the way it did when Timur held court there. These cities were not museum pieces to photograph and leave behind. They were living proof that the country had outlasted every empire that tried to absorb it — and they knew it.

Give this a like if you learned something new.

But pride in your own past is one thing. Opening your doors to the wider world is something else entirely.

---

## Chương 5

### Bản CŨ

Uzbekistan is one of the easiest countries on earth to get into. Not a claim. A fact. No embassy appointment. No weeks of paperwork. No visa fee, no invitation letter, no consulate visit. For citizens of more than eighty nations, the process is essentially nothing — you arrive, they stamp your passport, and you walk through. Up to thirty days, free and clear. It shares borders with five Central Asian neighbors — Kazakhstan, Kyrgyzstan, Tajikistan, Afghanistan, Turkmenistan — so you can also arrive by road, and the welcome is the same at every crossing.

And the language? Not the wall people expect. Two tongues run the country. Uzbek, the national language. And Russian, the residue of seven decades under Soviet administration. Russian is spoken widely enough that anyone over forty learned it in school, and anyone under forty picked it up through television, through film, through the simple momentum of a society that never stopped using it. But here is the part that catches travelers off guard. If you speak Turkish, you already understand more than you think. Uzbek is part of the same Turkic family, and the connection is not academic — it is audible. Words overlap. Grammar mirrors. A Turkish speaker can land in Tashkent and catch fragments of meaning — enough to order food, to ask a question, to follow the shape of a conversation without quite grasping every word. That mutual intelligibility runs through the whole Turkic-speaking belt, a linguistic thread older than every empire that ever tried to carve this region apart.

And once you are in — stamp in hand, language no longer a wall — the first sound that finds you is the bazaar. But what you will find there, and what it will cost you, is something almost nobody believes.

### Bản MỚI

For most of the modern era, this was not a place you could simply walk into. Closed frontiers. Soviet bureaucracy. A region the world forgot for nearly seventy years.

That has changed. Uzbekistan now offers visa-free entry for up to thirty days, to citizens of dozens of countries, with no embassy appointments and no advance paperwork. You land in Tashkent, you walk through the gate, and you are inside a country that for most of the twentieth century was almost impossible to reach. It shares borders with five Central Asian neighbors — Kazakhstan, Kyrgyzstan, Tajikistan, Afghanistan, Turkmenistan — which makes it a natural crossroads if you are moving through the wider region. But the real revelation is not where it sits on the map. It is how little friction there is at the door.

But a door that opens easily is only half the story. Once you are through it, the question becomes language, and here the surprise is how manageable it is. Uzbek and Russian are both widely spoken — Russian as the residue of empire, Uzbek as the tongue that came flooding back the moment independence permitted it. But here is what catches most travelers off guard. Uzbek is a Turkic language, which means it shares deep roots with Turkish, and through that family resemblance, it is mutually intelligible with Kazakh, Kyrgyz, and the other Turkic tongues that stretch across Central Asia. If you speak Turkish, you will catch fragments of conversation on the street. Not fluently. Not perfectly. But enough. Enough to ask a price. Enough to share a joke. Enough to feel, for a moment, that you are not entirely a stranger.

And once you stop feeling like a stranger, the bazaars are ready to prove it.


---

## 4. Mong team trả lời giúp

Đọc xong 5 chương ở trên, cho xin ý kiến — **không cần dài, mỗi câu một dòng là đủ**:

1. **Bản nào đọc trôi hơn khi đọc thành tiếng?** (đây là kịch bản voiceover, nên đọc to mới
   đúng cách kiểm.)
2. Bản cũ hay bị chê **"vụn, đọc như liệt kê"** — bản mới có đỡ hơn không, hay lại thành
   **dài dòng lê thê**?
3. Có chỗ nào trong bản mới **đọc thấy giả, thấy mùi AI** không? Chỉ giúp câu cụ thể.
4. Nếu phải giao cho nhân sự dựng video ngay hôm nay, **bản nào dùng được luôn**, bản nào
   phải sửa tay nhiều hơn?
5. Ngoài chuyện văn phong, còn lý do nào khác khiến team ngừng dùng công cụ không? (chờ lâu,
   hay lỗi, khó thao tác...)

---

## Ghi chú vận hành

- Bản mới chỉ chạy được **5/13 chương** thì **tài khoản GLM hết tiền** giữa chừng. Công cụ
  báo đúng lý do ("hết tiền, không phải nghẽn tốc độ"). **Cần nạp thêm tiền** thì team mới
  viết tiếp được.
- Thời gian chờ đo được từ nhật ký: trung vị **18 phút** một kịch bản, bài dài nhất 40 phút.
  Đây là do độ dài bài và tốc độ model, không phải treo.
- Từ nay mỗi lượt viết hỏng sẽ **ghi rõ lý do vào nhật ký** (trước đây 4 lượt hỏng không để
  lại nguyên nhân nào, không truy được).
