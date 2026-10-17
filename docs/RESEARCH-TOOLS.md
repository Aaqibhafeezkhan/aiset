# Araştırma araçları: sonuç raporu

Durum: 2026-10-17. Kullanım ve sınırlamalar için [README](../README.md#research-tools-teammap-impact-failures-relevant).

## Ne yapıldı

| Araç | Komut | Yeniden kullandığı altyapı |
|---|---|---|
| API değişiklik etkisi | `teammap impact <endpoint yolu \| fonksiyon \| Model> [METHOD]` | teammap index'i, `link()` (endpoint, model, frontend çağrısı), `call_sites`, `file_imports`, `mirror_types`, `model_uses`, episode okuyucu |
| Test hatası analizi | `teammap failures <dosya \| ->` | index (frame → çevreleyen fonksiyon), workspace veri alanı |
| Göreve ilişkin kod | `teammap relevant "<görev>"` | index'teki semboller, endpoint'ler, modeller; `brief_sections`, `read_episodes` |
| Kayıtlar | `teammap research show <id>`, `research list` | `<team>/graph/research/` |

- Kod: [src/aiset/research.py](../src/aiset/research.py). teammap bu alt komutları `arch` gibi ona devrediyor.
- Ortak işlevler kopyalanmadı. teammap'te `callers_of` ile `cmd_model` içindeki mantık `call_sites`, `model_uses`, `mirror_types` ve `import_resolver` fonksiyonlarına ayrıldı; mevcut komutların çıktısı aynı kaldı.
- Agent şablonları güncellendi: engineer (üçü birden), tester (`failures`), integration checker (`impact`), PM (`relevant`, `impact`). Hepsinde aynı kural var: önce kısa sonuç, sonra yalnızca gereken kod veya log satırları. `~` satırları ve "gaps" kodda doğrulanır. Sonuç boş ya da eksikse agent normal araştırmaya devam eder.
- Değerlendirme düzeneği: [eval/research_eval.py](../eval/research_eval.py) ve örnek workspace'in görevleri. Görev dosyası o workspace'in dosya adlarını içerdiği için aiset reposunda değil, workspace'in kendisinde: `example-usage/.claude/team/eval/tasks.json`.
- Yan düzeltme: Git Bash (agent'ların Windows'taki kabuğu) `/products` gibi argümanları `C:/Program Files/Git/products` yapıyordu. Bu yüzden `teammap endpoint /…` Windows'ta hiç eşleşmiyordu. `teammap` artık bu dönüşümü geri alıyor.

## Doğrulanan davranışlar

Otomatik testler: `python -m unittest discover -s tests` ile 23 testin hepsi geçiyor. Bunların 17'si yeni (`tests/test_research.py`).

- **Gerçek çıktılarla ayrıştırma:** pytest 8.4'ün dört traceback stili (long, short, native, `--tb=no`), Python 3.11 unittest, Node 20 test runner (TAP) ve JUnit XML gerçek çalıştırmalardan alındı. Jest ve Vitest örnekleri o araçlar kurulu olmadığı için formatlarına göre elle yazıldı; bu testler yalnızca ayrıştırıcıyı sınar.
- **Aynı hataların gruplanması:** Beş Python biçiminde de aynı beş test, aynı mesajlar ve iki testlik aynı `ValueError` grubu (`billing.py:6`, `parse_qty`) bulunuyor.
- **Frame sırası:** Python frame'leri dıştan içe yazılıyor, JavaScript frame'leri içten dışa. İkisinde de hatanın çıktığı en içteki frame doğru seçiliyor.
- **Kök neden:** Hiçbir grupta kök neden yazılmıyor (`root_cause: null`). Test çalıştırıcısının kendisi mesajı kısalttığında (`--tb=no`) bu bir boşluk olarak bildiriliyor.
- **Tanınmayan çıktı:** Sonuç "unrecognized" oluyor. Tahmin üretilmiyor.
- **Log güvenliği:** Logdaki `$(touch …)`, ters tırnak ve `python -c` komutları çalıştırılmıyor; test bunu bir işaret dosyasıyla doğruluyor.
- **Uçtan uca workspace testi:** FastAPI tarzı bir backend ile tsconfig alias'lı bir TS frontend üzerinde şunlar doğrulandı:
  - **Tüketiciler:** Aynı URL'ye giden `http.get` kesin eşleşme olarak bulunuyor. Aynı yol şekli ve metodla API istemcisindeki literal ve onu çağıran ekran çıkarım olarak bulunuyor. Aynı satır bloğundaki POST yanlışlıkla GET'e atfedilmiyor.
  - **Model ve sembol:** Alt sınıf, import eden dosyalar ve testler bulunuyor.
  - **Eşleşme olmayan sorgular:** Bulunamayan sembol "not-found", birden fazla endpoint'e uyan sorgu "ambiguous" sonucunu veriyor.
  - **Index yokken:** Repo tanımlı değilse sonuç "no repositories to index" diyor.
- **Önbellek:** Aynı çağrı ikinci kez yapılınca kayıttan geliyor. İlgili dosya commit edilmeden değiştirilince sonuç yeniden hesaplanıyor; yeni çağıran da sonuca giriyor ve `uncommitted ≥ 1` görünüyor.
- **Araç kodu değişince:** Araç kodu da fingerprint'e dahil. Geliştirme sırasında eski bir sonucun "geçerli" diye döndüğünü görüp bunu ekledim.
- **Çıktı sınırı:** `--max-chars` ve `--limit` kesilen kısmı adıyla bildiriyor; `research show` kalan satırları gösteriyor.
- **Repolar:** Bütün çağrılardan sonra repoların `git status` çıktısı aynı kalıyor.

Aşağıdaki karşılaştırma ve ölçümler gerçek bir workspace'te yapıldı: FastAPI backend (`example-api`) ve Next.js frontend (`example-web`), toplam 297 dosya. Proje, repo, dosya ve endpoint adları örnek adlarla değiştirildi; satır numaraları ve sayılar ölçülen değerlerdir.

Örnek workspace üzerinde elle karşılaştırma (araç çıktısı ile `git grep`):

| Sorgu | Araç | grep ile kontrol |
|---|---|---|
| `GET /products/` tüketicileri | `api-client.ts:202` ve `api.products.list()` çağıran 6 yer | 6 çağrının 6'sı, fazlası yok |
| `GET /products/{id}` | `api-client.ts:203` ve 2 çağıran | 2'nin 2'si |
| `PATCH /products/{id}` | `api-client.ts:207` ve `product-management.tsx:86` | aynı |
| `DELETE /products/{id}` | `api-client.ts:210`, çağıran yok | `products.remove(` hiç geçmiyor |
| Testler | yok | `app/tests/test_product.py` boş bir dosya; "test yok" doğru |

## Ölçülen sonuçlar (size modu, gerçek agent çalıştırması değil)

Örnek workspace'in aynı durumu üzerinde, betiklenmiş adımlarla ölçüldü. Baseline, bugünkü yol: mevcut teammap sorgusu, ardından grep ve okumalar. Treatment ise araştırma komutu ve doğrulamak için yapılan okuma. Değerler token değil, karakterdir.

| Görev | Adım (baseline → araç) | Okuma | Çıktı karakteri | Beklenen bilgi |
|---|---|---|---|---|
| PATCH tüketicileri | 5 → 2 | 2 → 1 | 4.260 → 2.287 | 2/2 → 2/2 |
| GET liste tüketicileri | 5 → 2 | 2 → 1 | 5.599 → 2.827 | 4/4 → 4/4 |
| `ProductResponse` kullanımı | 2 → 1 | 0 → 0 | 1.687 → 2.167 | 3/3 → 3/3 |
| Batch stok düzeltmesinin yeri | 3 → 2 | 1 → 1 | 5.163 → 5.495 | 4/4 → 4/4 |
| Başarısız test triyajı | 1 → 1 | 1 → 0 | 3.932 → 2.112 | 5/5 → 5/5 |
| **Toplam** | **16 → 8** | **6 → 3** | **20.641 → 14.888** | aynı |

Index maliyeti (örnek workspace: 297 dosya): soğuk `teammap index --force` 1,2 s, sıcak 0,2–0,3 s. Index 2,1 MB, kayıtlar yaklaşık 0,14 MB. Araştırma komutu başına süre 0,3–0,4 s; bunun çoğu index'in güncellenmesi.

Nasıl okunmalı:
- **Karışık sonuç:** Beş görevin ikisinde araç çıktısı daha uzun.
  - `ProductResponse` görevinde mevcut `teammap model` zaten kısa bir yanıt veriyordu. `impact` buna boşlukları, importları ve kayıt satırını ekliyor.
  - Batch görevinde baseline, aranacak kelimeyi (`adjust`) önceden bildiğim için hedefli kaldı. Kelimeyi bilmeyen bir agent daha fazla arama yapardı, ama bu ölçülmedi.
- **Baseline'ın sınırı:** Baseline adımlarını ben yazdım. Gerçek bir agent daha az ya da daha çok adım atabilir.
- **Doğruluk:** Doğruluk, beklenen dosya ve sembol adlarının çıktıda geçip geçmediğiyle ölçüldü. Cevabın tamamının doğruluğu ölçülmedi.

## Henüz doğrulanmamış varsayımlar

- **Token tasarrufu kanıtlanmadı.** Gerçek agent çalıştırması yapılmadı. Tasarrufu ölçmek için agent modu kullanılmalı:
  ```sh
  python eval/research_eval.py <example-usage>/.claude/team/eval/tasks.json --workspace <example-usage> --mode agent --confirm-cost --runs 3
  ```
  Bu mod Claude Code'un bildirdiği giriş, çıkış, önbellekten okuma ve önbelleğe yazma token'larını, araç çağrılarını, okumaları, tur sayısını, süreyi ve maliyeti kaydeder. Her çalıştırmadan önce ve sonra repoların aynı durumda olduğunu doğrular. Para harcadığı için çalıştırılmadı.
- **Neden azalabilir:** Daha az tur ve daha az okuma, her turda yeniden gönderilen bağlamı azaltmalı. Ancak bu araç çıktısının agent tarafından doğru kullanılmasına bağlı. Agent `~` satırlarını doğrulamak için yine kod okuyacak.
- **Neden artabilir:** Agent sonuca güvenmeyip yine grep yaparsa, maliyet araç çıktısı kadar artar.
- **Önbelleğin katkısı küçük:** Fingerprint hesabı index'i zaten güncellediği için kayıt, hesaplamadan yalnızca birkaç yüz milisaniye kazandırıyor. Asıl değeri, aynı sorunun aynı kayıt kimliğiyle izlenebilmesi.

## Bilinen sınırlamalar (bu sürüm)

- **Dil:** Yalnızca Python ve TypeScript. Örnek workspace'te başka dilde repo yok.
- **Ada göre eşleştirme:** Çağıranlar adla eşleşiyor. Aynı adlı başka fonksiyonlar karışabilir; dependency injection üzerinden yapılan çağrılar kaçabilir.
- **`relevant` yalnızca kelime eşleştiriyor:** Türkçe bir görev açıklaması İngilizce kodla eşleşmiyor ("ürün partisi stok düzeltmesi" sorgusu sonuç vermedi ve bunu açıkça söylüyor).
- **Zayıf ayna tipi tahmini:** Frontend ayna tipi tahmini (teammap `model` komutundan devralındı) zayıf adaylar verebiliyor. Örneğin `Warehouse` tipi `ProductResponse` için 6 ortak alanla listelendi; satır inferred olarak işaretli.
- **Yalnızca belirli formatlar:** `failures` yalnızca listelenen formatları tanıyor. Jest ve Vitest örnekleri gerçek bir çalıştırmadan alınmadı.
