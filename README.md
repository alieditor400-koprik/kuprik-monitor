# Ko‘prik monitoringi

Ko‘prik reyestri, GIS xaritasi, pasport va dala tekshiruvi jurnali. Interfeys telefon va noutbuk uchun moslashadi.

## Uch usulda ishga tushirish

### Darhol sinab ko‘rish

Brauzerda index.html faylini oching. Namuna pasportlarini ko‘ring va hisobotlarni yuklab oling. Xizmat ma’lumotlarini jamoaviy rejimda kiriting.

### Windows va Wi-Fi

Python 3.10+ bilan Boshlash.bat faylini ishga tushiring. Brauzerda http://localhost:8765 manzili ochiladi. Dastur oynasidagi kirish kodini kiriting. Telefonlar uchun Tarmoqda-boshlash.bat faylini ishga tushiring. Oynada Wi-Fi IPv4 manzilini topib, telefon brauzerida, masalan, http://192.168.1.20:8765 manzilini oching. Windows so‘rasa, faqat shaxsiy tarmoqqa ruxsat bering. Kompyuter ishlab turishi va telefon shu Wi-Fi tarmog‘ida bo‘lishi kerak.

### GitHub va internet

1. Paketdagi fayllarni yangi GitHub repozitoriysiga yuklang. Jamoaviy ma’lumotlar, parollar va bazani repozitoriydan tashqarida saqlang.
2. GitHub Pages uchun Settings → Pages → Deploy from a branch → main → / (root) ni tanlang. Shu manzilda mustaqil sinov versiyasi ishlaydi.
3. Umumiy bazali versiya uchun Docker Compose mavjud serverga repozitoriyni oling. Domenning DNS yozuvini serverga yo‘naltiring va 80 hamda 443 portlarini oching.
4. Serverda .env.example faylidan .env yarating va BRIDGE_DOMAIN qiymatiga haqiqiy domenni yozing. accounts.example.json dan accounts.json yarating. Har bir xodimga alohida login va kamida 16 belgili tasodifiy parol belgilang. accounts.json fayliga serverda cheklangan fayl ruxsatini bering. admin pasportlarni va xodimlar ruxsatlarini boshqaradi. inspector administrator yozish ruxsatini berganda pasport va jurnalni yuritadi. Jurnal muallifi hisobdan olinadi.
5. Serverda docker compose up -d --build buyrug‘ini bajaring. Domen orqali HTTPS bilan kiring. Hisoblarni o‘zgartirgandan keyin docker compose restart app ni bajaring.
6. Ma’lumotlar database nomli doimiy Docker jildidagi /data/monitoring.sqlite3 fayliga yoziladi. Zaxiralash uchun ilovani to‘xtating, bazaning nusxasini oling va ilovani qayta ishga tushiring. docker compose down -v bu jildni o‘chiradi.

## Monitoring

Ko‘prikning ko‘rsatiladigan holati oxirgi dala tekshiruvidan olinadi. Uskunalar va onlayn sonini administrator kiritadi. Tashqi BIM modeliga havola pasportdan ochiladi. Datchik telemetriyasi, video va muhandislik hisoblari uchun qurilma protokollari, sinov ma’lumotlari va tasdiqlangan mezonlar kerak.

Interaktiv hudud xaritasi sahifaga biriktirilgan va internetga ulanmasdan ishlaydi.
 
## Xarita ma’lumotlari

Chegaralar geoBoundaries gbOpen UZB ma’lumotlari asosida soddalashtirib ko‘rsatilgan. ADM1 2017 chegaralari © OpenStreetMap ishtirokchilari, ODbL 1.0. ADM2 2020 chegaralari OCHA ROCCA, CC BY 3.0 IGO. Ushbu tarixiy xarita versiyasida yangi ma’muriy o‘zgarishlar yetishmasligi mumkin.

- ADM1 manbasi: https://www.geoboundaries.org/api/current/gbOpen/UZB/ADM1/
- ADM2 manbasi: https://www.geoboundaries.org/api/current/gbOpen/UZB/ADM2/
- ODbL: https://opendatacommons.org/licenses/odbl/1-0/
- CC BY 3.0 IGO: https://creativecommons.org/licenses/by/3.0/igo/
 
## Admin paneli va hisobotlar

- Brauzer demosida xarita, namunaviy pasportlar va CSV hisobotlari mavjud. Ko‘prik qo‘shish, tahrirlash va xodimlarni boshqarish uchun serverli versiyaga kiring.
- Serverli versiyada administrator “Admin paneli” → “Mutaxassis qo‘shish” orqali individual hisob yaratadi. “Pasport qo‘shish va tahrirlash” belgisini yoqing yoki keyinroq ro‘yxatdan ruxsat bering. Ruxsat bekor qilinganda xodim pasport, jurnal va hisobotlarni ko‘rishi mumkin.
- Pasport o‘zgarishlari foydalanuvchi, vaqt va yangilangan maydonlarning oldingi hamda yangi qiymatlarini saqlaydi. Avvalgi versiyadagi pasportlarda eski muallif yoki vaqt qayd etilmagan bo‘lsa, ular bo‘sh ko‘rsatiladi.
- Windowsdagi standart kirish kodi “Administrator” nomi bilan qayd etiladi. Shaxsiy administrator hisobi kerak bo‘lsa, PowerShell orqali BRIDGE_ACCOUNTS_FILE muhit o‘zgaruvchisiga accounts.json faylining to‘liq manzilini belgilang va serverni ishga tushiring. HTTPS rejimi uchun Compose yo‘riqnomasidan foydalaning.
- “Reyestr CSV” joriy hudud va qidiruv filtrlariga mos ro‘yxatni yuklaydi. Pasportdagi “Hisobotni yuklash” maydonlar, jurnal va o‘zgarishlar tarixini CSV sifatida beradi. Fotosurat bilan hisobot uchun “Chop etish / PDF” dan foydalaning.
- Bosh sahifadagi ko‘prik tasvirlari O‘zbekiston manzaralaridan ilhomlangan ilustratsiyalar. Tasvirni qo‘lda tanlash va avtomatik almashishni to‘xtatish mumkin.

Xarita, reyestr, pasportlar, jurnal va hisobotlar kirishsiz ochiladi. Xodimlar yuqori menyudagi «Xodimlar kirishi» orqali tizimga kiradi.

Admin paneli yuqori menyuda ochiladi. Har bir mutaxassis Xodim rolini oladi. Ism, login, bo‘lim yoki lavozim bo‘yicha qidirish mumkin. Xodim profili faqat administratorga ko‘rinadi. Diagnostika jurnalida bajarilgan sana va kiritilgan soat, xodim ismi hamda tizimga yozilgan vaqt ko‘rinadi. Ko‘prik pasportida surat va koordinata saqlanadi. GPS HTTPS yoki localhost orqali, qurilma ruxsati bilan ishlaydi. Koordinatani qo‘lda ham kiritish mumkin.
