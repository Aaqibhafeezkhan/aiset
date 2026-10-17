# aiset: özellik envanteri

Durum: 2026-10-15. Bu belge sistemde şu an neyin olduğunu ve neyin eksik olduğunu tek yerde toplar; bir sonraki geliştirmeyi seçmek için kullanılır. Ayrıntılı kullanım için [README.md](../README.md).

İşaretler: ✅ çalışıyor · 🟡 kısmen / sınırlı · ❌ yok

## 1. Takım ve iş akışı

| Özellik | Durum | Kısaca |
|---|---|---|
| Tester | ✅ | Değişen repolarda test, lint ve type-check çalıştırır, gerekirse test yazar. `STATUS: pass/fail`. |
| Integration checker | ✅ | Servisler arası sözleşmeyi (API alanları, tipler, enum'lar, ortak tablolar) kontrol eder. Salt okunur. |
| AWS ve Teleport agent'ları | ✅ | Altyapı soruları; değişiklikler kullanıcı onayına kadar yalnızca öneri. |
| Task board | ✅ | İstek başına ortak hafıza: `brief.md` (hedef, kriterler, kararlar), `contract.md` (API şekli), `handoff/<agent>.md`, `log.md`. PM agent'lar arasında mesaj taşımaz. |
| Episode'lar | ✅ | Task kapanınca PM'in yazdığı kısa özet (görev, ajanlar, sonuç, dokunulan dosyalar, kararlar, tuzaklar). Sonraki işlerde okunur. |
| Rapor formatı | ✅ | Her agent `STATUS:` satırıyla biter; ofisteki task board sütunları buradan çıkar. |
| `MODEL:` satırı | ✅ | PM her atamada modeli ve gerekçesini yazar; ofis bunu atama kartında gösterir. |
| Knowledge brief'leri | ✅ | Agent başına uzun süreli hafıza; agent'lar `## Field notes` altına öğrendiklerini ekler. PM'den "refresh … knowledge" ile yeniden üretilir. |
| Brief index'leri | ✅ | `brief_index.py`, her brief için bölüm, satır aralığı ve token boyutu tablosu yazar; agent'lar önce index'i, sonra yalnızca gereken bölümü okur. Ofis bayatlayanları her yoklamada yeniler. |
| Herhangi bir projeye kurulum | ✅ | `init_team.py <klasör>`: repoları tarar, stack'i tanır, repo başına engineer, PM, tester ve integration checker üretir; her şeyi `<klasör>/.claude` altına yazar. Birden fazla takım yan yana yaşayabilir. |
| Monorepo ve stack'e göre ekip | ✅ | Kök klasör tek git reposuysa servis klasörleri birim olur; 12'den fazla birimde (ya da `--group stack`) Java, Node, Python ve DevOps için birer engineer. DevOps kökteki CI ve build dosyalarının sahibi. Takım dosyaları `.git/info/exclude` ile yerelde kalır (`--share` ile paylaşılır). `tkm-microservices` (52 servis) ile kuruldu. |
| Roster ve yeniden adlandırma | ✅ | İsimler `roster.json`'da; ofis değişikliği birkaç saniyede agent dosyalarına kopyalar (`sync_names.py`). |
| Yardımcı agent'lar (`helpers`) | ✅ | Explore, Plan ve general-purpose gibi yerleşik agent'lar roster'da yeniden adlandırılabilir. |

## 2. Ofis arayüzü (`/`)

| Özellik | Durum | Kısaca |
|---|---|---|
| İzometrik ve klasik görünüm | ✅ | Odalar, masalar, animasyonlu botlar; sağ üstten klasik kart düzenine geçiş. Seçim tarayıcıda hatırlanır. |
| Agent durumları | ✅ | Çalışıyor, düşünüyor, seni bekliyor, bitti, boşta; animasyon ve renkle. |
| Konuşma balonları | ✅ | Agent'ın o an ne yaptığı. |
| Atama çizgileri | ✅ | PM'den çalışan agent'lara akan çizgiler. |
| "Needs you" uyarısı | 🟡 | PM soru sorduğunda kırmızı banner. İzin istemleri transcript'e yazılmadığı için "onay mı bekliyor?" yalnızca 2 dakikalık sessizlikten tahmin edilir. |
| Task board sekmesi | ✅ | Atamalar sütunlarda: netleştirme bekleyen, sürüyor, review'dan dönen, bitti. |
| Tasks sekmesi | ✅ | PM task'ları; kartta toplam token, tahmini maliyet, agent'lara bölünmüş çubuk, agent başına pay. |
| Task detayı: Overview | ✅ | Tüm agent'ların token toplamı, agent bazında tablo (çalışma, token, maliyet, pay), çalışma listesi, board içeriği ve episode. |
| Task detayı: Agent routes | ✅ | Her agent'ın o task'ta nerelere uğradığı: dosya × agent tablosu (düzenledi / okudu / aradı), repo filtresi, adım adım rota, dosyaya tıklayınca yalnızca o dosyanın adımları. Bash ile yapılan okumalar da çözümlenir. |
| Agent detayı | ✅ | Brief durumu, son atamalar, görev metni, rapor, token dökümü, aktivite akışı. |
| Live feed | ✅ | Tüm takımın tool çağrıları ve mesajları, zaman sırasıyla. |
| Doğrudan bağlantılar | ✅ | `#open=<agent>`, `#tab=boards`, `#open=task:<id>&view=routes`. |
| Modern tema | ✅ | Grafit renkler, cam efektli paneller, Inter ve JetBrains Mono, klavye odak halkaları, hareket azaltma desteği. Yalnızca koyu tema. |
| Ayarlar sayfası (`/settings`) | ✅ | Agent başına model (agent dosyasının `model:` satırına ve PM'in "Pinned models" bölümüne yazılır), isim, rol, renk, görev; takım adı ve PM komutu; side panel sekmeleri, odalar, sayfalar ve göstergeler açılıp kapanır (sekmelerde × da var); zaman pencereleri yeniden başlatmadan değişir. `<team>/settings.json` (2026-10-17). |

## 3. Token ve maliyet takibi

| Özellik | Durum | Kısaca |
|---|---|---|
| Mesaj başına token | ✅ | Fresh input, cache write, cache read ve output; transcript'ler artımlı okunur. |
| Tahmini maliyet | ✅ | Liste fiyatlarıyla (`PRICES`, `core.py`). Cache yazmaları TTL'ine göre: alt-agent'lar 5 dakika, lead oturumları 1 saat. |
| Task başına toplam | ✅ | Board ya da episode adıyla eşleştirme. Alt-agent'lar kesin; PM'in payı turlarının hangi task'a ait olduğuna göre tahmini. |
| Bağlam boyutu | ✅ | Her agent'ın o anki tur başına bağlamı. |
| Takım ve tüm oturumlar toplamı | ✅ | Üst barda, seçili zaman penceresi için. |
| Zaman içinde maliyet | ❌ | Günlük veya haftalık trend, task türüne göre ortalama, önce/sonra karşılaştırması yok; her şey pencereden anlık hesaplanıyor. |
| Bütçe uyarısı | ❌ | Bir task veya agent belli bir tutarı geçince uyarı yok. |

## 4. Brain (`/brain`)

| Özellik | Durum | Kısaca |
|---|---|---|
| Bilgi grafiği | ✅ | Agent'lar, brief'ler ve bölümleri, repolar, dosyalar, episode'lar; yanında ağaç görünümü. |
| Kod grafiği | ✅ | `teammap`'in endpoint, model ve API çağrısı düğümleri; `graph/*.json` ile başka indeksleyiciler de eklenebilir. |
| Canlı izler | ✅ | Çalışan agent'ların son adımları haritada oklarla; "Follow" kamerayı agent'ta tutar. |
| Task haritası | ✅ | `#task=<id>`: yalnızca o task'ta uğranan düğümler ve her agent'ın rotası; seçili agent belirgin. |
| Arama, odaklanma, filtre | ✅ | `/` ile arama, çift tıkla komşuluk, tür filtreleri. |

## 4b. Mimari haritası (`/architecture`)

| Özellik | Durum | Kısaca |
|---|---|---|
| Repo profili | ✅ | Diller (oranlarıyla), framework, repo türü (frontend, gateway, API, servis, worker, pipeline, registry, kütüphane), stack, nasıl çalıştığı, build ve deploy. Python, Node/TypeScript ve Java/Kotlin (Spring); monorepo'da servis başına. |
| Altyapı bileşenleri | ✅ | Kurala dayalı detector'lar: PostgreSQL, MySQL, MongoDB, SQLite, Redis, Celery, RabbitMQ, Kafka, Keycloak, JWT, S3, GCS, MinIO, BigQuery, Elasticsearch, Sentry, Airflow, zamanlanmış işler, SMTP, WebSocket. Güven seviyesi ve `dosya:satır` kanıtıyla. |
| Servisler arası bağlantılar | 🟡 | Kesin: frontend → backend URL eşleşmesi, `@FeignClient`, Zuul/Gateway route'ları, servis adını içeren URL'ler, Eureka kaydı. Tahmini: client sınıfı ve URL ayarı adı. Kuyruk üretici/tüketici eşleşmesi henüz yok. |
| Sistem haritası | ✅ | Dört katman (istemciler, servisler, async, altyapı), türe göre renkli oklar, seçince yalnızca ilgili bağlantılar, kanıt paneli, VS Code'da açma. |
| Mermaid çıktısı | ✅ | Haritayı docs ve PR'lar için Mermaid olarak verir. |
| `teammap arch` | ✅ | Aynı bilgi agent'lar için kısa metin. |
| İstek akışı | ❌ | Endpoint → servis → DB → dış çağrı → async devam şeması (3. aşama). |
| Elle düzeltme dosyası | ❌ | `architecture.yml` (2. aşama). |

## 5. Token tasarrufu önlemleri

| Özellik | Durum | Kısaca |
|---|---|---|
| Tool whitelist'leri | ✅ | Her agent'ta `tools:` satırı; başlangıç bağlamı yaklaşık 31k yerine 5–8k. |
| `teammap` kod haritası | ✅ | `endpoint`, `symbol`, `model`, `file`, `search`: "nerede, kim kullanıyor" sorusunu tek çağrıda cevaplar. Python `ast`, TypeScript repo'nun kendi derleyicisiyle. |
| `teammap arch [repo]` | ✅ | Repo'nun stack'i, nasıl çalıştığı, kullandığı altyapı ve çağırdığı servisler, tek çağrıda. |
| Araştırma araçları | ✅ | `teammap impact` (endpoint, fonksiyon veya model değişikliğinin etkisi), `teammap failures` (kaydedilmiş test çıktısından hata grupları), `teammap relevant` (göreve ilişkin dosya, sembol, brief bölümü ve episode). Kesin/çıkarım ayrımı, kapsam boşlukları, girdi parmak izine bağlı kayıtlar (`<team>/graph/research/`). Ayrıntı ve ölçümler: [RESEARCH-TOOLS.md](RESEARCH-TOOLS.md). |
| `teammap code <isim>` | ✅ | Tek bir fonksiyonun yalnızca kendi kodu, satır numaralarıyla; sınıflarda başlık ve metot listesi. "Grep ile bul, sonra oku" iki turunu teke indirir. |
| Okuma kuralları | ✅ | Ölçüme dayalı: birlikte gereken parçalar tek Bash çağrısında, düzenlenecek kısım `offset`/`limit` ile Read, asla bütün uzun dosya. DB sorgularında `LIMIT`, testlerde önce dar hedef. |
| Atama boyutu | ✅ | 40–60 tool çağrısına sığan işler; daha büyüğü sıralı parçalara bölünür. |

## 6. Altyapı

| Özellik | Durum | Kısaca |
|---|---|---|
| Bağımlılıksız | ✅ | Yalnızca Python 3 standart kütüphanesi; TypeScript ayrıştırması için repo'nun kendi `typescript` paketi. |
| Salt okunur | ✅ | Claude Code'un zaten yazdığı transcript'leri okur; hiçbir şeye yazmaz (brief index'leri ve isim senkronu hariç). |
| Windows desteği | ✅ | Yol normalizasyonu, `\` ve `/` ayırıcıları. |
| Komutlar | ✅ | `pip install -e .` ile `aiset`, `aiset-init` ve `teammap` komutları gelir (`pyproject.toml`). Kurulumsuz da `python src/aiset/<modül>.py` çalışır. Kod 2026-10-17'de `src/aiset/` paketine taşındı (proje adı agent-office → aiset). |
| Otomatik testler | 🟡 | `tests/`: task kimlikleri, import çözümü ve araştırma araçları (gerçek pytest/unittest/Node çıktılarıyla ayrıştırıcılar; küçük bir workspace üzerinde uçtan uca). Transcript ayrıştırma (`core.py`) için hâlâ test yok. |
| Windows Git Bash argümanları | ✅ | Git Bash `/products` gibi argümanları `C:/Program Files/Git/products` yapıyor; `teammap` bunu geri çeviriyor (2026-10-17). |

## Eksikler ve öneriler

Öncelik sırasıyla. "Etki", çözülünce ne kazanılacağını anlatır.

| # | Eksik | Neden önemli | Öneri |
|---|---|---|---|
| 1 | ~~**Şablondaki board adı biçimi uyumsuz (hata)**~~ ✅ 2026-10-17 | Şablon artık `<yyyy-mm-dd>-<slug>` kullanıyor; `core.py` eski `<yyyymmdd>-<slug>` board'ları da tanıyıp aynı task anahtarına (`task_id`) çeviriyor, böylece eski board'lar episode'larıyla eşleşiyor. | Mevcut takımların agent dosyaları `init_team.py` ile yeniden üretilmeli. |
| 3 | **Kuralların etkisi ölçülmedi** | Model seçimi, okuma ve cache kuralları veriye dayanıyor ama sonrası ölçülmedi. | Ofise "dönem karşılaştırması": task başına $, Sonnet/Opus oranı, çağrı başına bağlam, geç devamdan gelen cache yazması; önce/sonra. |
| 4 | **Maliyet geçmişi yok** | Her şey zaman penceresinden anlık hesaplanıyor; trend ve ortalama görülemiyor. | Kapanan task'ların token ve maliyetini episode'a ya da küçük bir JSON/SQLite dosyasına yaz; Tasks sekmesine trend grafiği. |
| 5 | **Bütçe ve anomali uyarısı yok** | 22M token'lık bir task ancak sonradan fark edildi. | Task veya çalışma başına eşik; aşınca kart ve banner'da uyarı, isteğe bağlı bildirim. |
| 6 | **Otomatik test yok** | Ayrıştırma ve eşleştirme sezgisel; Claude Code transcript formatı değişirse sessizce bozulur. | Örnek transcript'lerle `core.py` (task eşleştirme, `bash_targets`, maliyet) için küçük bir test seti. |
| 7 | **İzin isteği tespiti tahmini** | "Onay mı bekliyor?" 2 dakikalık sessizliğe dayanıyor; yanlış alarm ya da gecikme olabiliyor. | Claude Code hook'u (ör. bildirim hook'u) ile durumu bir dosyaya yazıp ofiste okumak. |
| 8 | **`teammap` sıralaması** | Aynı isimli tanımlarda v1 dosyası v2'nin önüne geçebiliyor (ör. `buildDriverShiftRows`). | Son değişen dosyayı veya aktif modülü öne alan sıralama; `--repo`/yol filtresi önerisi. |
| 9 | **Rota çözümlemesi sınırlı** | Bash çözümleyici yaygın kalıpları tanıyor; `python -c` ile okumalar, boşluksuz `>dosya`, dinamik yollar kaçıyor. Agent başına son 600 adım gösteriliyor. | Kaçan kalıpları ölçüp ekle; rotada "çözülemeyen komut" sayısını göster. |
| 10 | **Eski kopya duruyor** | Git dışındaki `~/projects/learnings/agent-office` hâlâ var; değişikliklerin yanlış yere yapılmasına bir kez yol açtı. | Sil ya da repoya sembolik bağlantı yap. |
| 11 | **Açık tema yok** | Arayüz yalnızca koyu. | İsteğe bağlı açık tema. |

Yukarıdaki maddelerden biri seçildiğinde bu tablo güncellenmeli: biten madde ilgili bölüme ✅ olarak taşınır.
