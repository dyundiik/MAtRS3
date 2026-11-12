# TripPack — ПЗ3

Реалізація обов'язкових сервісів TripPack на Python/FastAPI.

## Склад
- Auth Service: реєстрація, вхід, вихід на клієнті, профіль, ролі user/admin.
- Trip Service: CRUD поїздок і контроль власника.
- Packing Service: списки для поїздок, речі, категорії, фільтрація, статус пакування, спільний доступ.
- Categorization Service: довідник категорій, типи поїздок, класифікація назви, автоматичні рекомендації речей.
- PostgreSQL: окремі БД auth_db, trip_db, packing_db.
- API Gateway, RabbitMQ (інфраструктурна готовність), Prometheus, Grafana.

## Запуск
1. Скопіюйте `.env.example` у `.env` та замініть секрети.
2. Запустіть `docker compose up --build -d`.
3. Перевірте `docker compose ps`.
4. Відкрийте http://localhost:8080 та API docs через адреси нижче.

## API
- Auth: http://localhost:8000/api/auth/docs
- Trips: http://localhost:8000/api/trips/docs
- Packing: http://localhost:8000/api/packing/docs
- Categories: http://localhost:8000/api/categories/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

## Основний сценарій
1. POST `/api/auth/auth/register` — створити користувача.
2. POST `/api/auth/auth/login` — отримати JWT.
3. У Swagger натиснути Authorize та ввести `Bearer <token>` (або передати Authorization header).
4. POST `/api/trips/trips` — створити поїздку.
5. POST `/api/packing/lists` — створити список із `trip_id`, `title`, `trip_type`.
6. Packing Service запитує Categorization Service та додає стартові речі для типу поїздки.
7. GET `/api/packing/lists/{id}/items?category=одяг` — фільтрація.
8. PUT `/api/packing/items/{id}` з `{"is_packed":true}` — позначити спакованим.

## Примітка про gateway
Шляхи проксіруються без початкового префікса сервісу: `/api/auth/` -> Auth Service `/`, тому фактичні endpoint-и доступні як `/api/auth/auth/register`, `/api/auth/users/me` тощо. Аналогічно для інших сервісів.

## Безпека
За наявності ADMIN_EMAIL та ADMIN_PASSWORD у .env Auth Service створює початковий обліковий запис адміністратора під час першого запуску. Паролі хешуються bcrypt. JWT підписується спільним секретом і має строк дії 8 годин. Списки мають власника та перелік user_id зі спільним доступом. У production потрібні HTTPS, ротація секретів, окремі DB-користувачі та перевірка JWT revocation/introspection. Logout у цьому навчальному варіанті означає видалення токена клієнтом.
