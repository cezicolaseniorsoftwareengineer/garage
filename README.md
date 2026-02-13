# GARAGE

<img width="1914" height="967" alt="image" src="https://github.com/user-attachments/assets/24db1bd1-4c19-4169-b6fc-6a16e91e8425" />


<img width="1873" height="905" alt="image" src="https://github.com/user-attachments/assets/311086dc-5da8-4d30-a07a-a1c69ead0c7e" />


<img width="1906" height="891" alt="image" src="https://github.com/user-attachments/assets/53189e6e-dcb3-46fe-9ed0-cba4304ea1f5" />



> Every Big Tech started in a garage.

2D platformer game about the history of computing. The player walks through Silicon Valley from 1973 to 2026, meeting real tech founders, answering engineering challenges, and leveling up from Intern to Principal Engineer.

Built with Python/FastAPI on the backend and HTML5 Canvas on the frontend. The architecture follows DDD with hexagonal layers -- domain logic is decoupled from the HTTP framework.

## How to run

```bash
cd Garage
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open `http://localhost:8000/static/index.html`.

## Locations

The game covers 12 real-world locations across 6 acts:

- Xerox PARC (1973) -- OOP, Binary, Boolean Logic
- Apple Garage (1976) -- Algorithms, Big O, Memory
- Harvard / Microsoft (1975) -- Data Structures, Compilers
- Amazon Garage (1994) -- Monoliths, SQL/ACID, Hash
- Stanford / Google (1998) -- Sorting, PageRank, Indexing
- PayPal / X.com (2000) -- Security, Cryptography, Transactions
- Harvard Dorm (2004) -- Graph Theory, REST APIs, OAuth
- AWS Re:Invent (2015) -- Microservices, Containers, CAP Theorem
- MIT 6.824 (2016) -- Raft, Event Sourcing, CQRS, Kafka
- Google SRE HQ (2016) -- SLI/SLO/SLA, Observability
- Enterprise Architecture (2020) -- SOLID, Clean Code, DDD
- The Final Arena (2026) -- Refactor your own legacy code

## Stack

- Backend: Python 3.12, FastAPI, Pydantic
- Frontend: HTML5 Canvas, Vanilla JS, CSS
- Persistence: JSON files (Supabase planned for v3)
- Architecture: DDD + Hexagonal + CQRS

## Project layout

```
Garage/
  app/
    domain/          -- entities, enums, scoring, invariants
    application/     -- use cases (start_game, submit_answer, etc.)
    infrastructure/  -- JSON repos
    api/routes/      -- FastAPI endpoints
    static/          -- frontend (HTML, JS, CSS, sprites)
    data/            -- challenges.json, sessions.json
```

## Author

Cezi Cola -- Bio Code Technology ltda
