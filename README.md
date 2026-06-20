# CM-Dashboard (Complaint Intelligence System) 🚨

> A scalable, AI-powered backend system for civic complaint management, routing, and rapid response coordination.

**CM-Dashboard** is a robust backend system designed to manage, analyze, and coordinate responses to civic complaints (e.g., sanitation, water supply, roads). Built with modern AI and Python technologies, it provides a powerful multi-stage pipeline utilizing PyTorch multi-label classification, FAISS-based Retrieval-Augmented Generation (RAG), and a sequential Decision Agent architecture to automatically categorize and route issues to the correct departments.

---

## ✨ Core Features

- **Multi-Label AI Classification**: Automatically tags incoming complaints with categories using a fine-tuned PyTorch `BCEWithLogitsLoss` model with dynamic threshold tuning.
- **RAG Memory Integration**: Leverages `sentence-transformers` and `FAISS` to fetch historical context on similar complaints, ensuring routing consistency.
- **Sequential Decision Agent**: An orchestrated agent pipeline that cross-validates ML predictions against historical consensus to output highly accurate, structured routing JSON responses.
- **Robust Authentication & Routing**: Secure RESTful FastAPI endpoints handling both synchronous and asynchronous operations.
- **End-to-End Evaluation**: Automated evaluation pipeline outputting ROC-AUC curves, confusion matrices, and metrics.

## 🛠️ Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) - High performance API routing.
- **AI / ML**: [PyTorch](https://pytorch.org/), [Sentence-Transformers](https://sbert.net/), [scikit-learn](https://scikit-learn.org/)
- **Vector Database**: [FAISS](https://github.com/facebookresearch/faiss) - Fast similarity search.
- **Database**: [PostgreSQL](https://www.postgresql.org/) via SQLAlchemy and Alembic.

---

## 📂 Project Structure

```text
CM-Dashboard/
├── CM-Dasboard/
│   ├── app/
│   │   ├── api/            # FastAPI routers (e.g., /complaints, /pipeline)
│   │   ├── ml/             # PyTorch training loops, datasets, evaluation code
│   │   ├── models/         # SQLAlchemy ORM entities
│   │   ├── schemas/        # Pydantic models for validation
│   │   └── services/
│   │       ├── agents/     # Decision Agent orchestrator & modular components
│   │       ├── memory/     # FAISS RAG and vector retrieval
│   │       └── ml/         # ML inference loaders
│   ├── tests/              # Pytest logic with mocked ML/FAISS
│   └── .env.example        # Environment variables
├── scripts/                # End-to-end execution and output generation scripts
├── outputs/                # Evaluation metrics, JSON results, and confusion matrices
└── logs/                   # Pipeline execution logs
```

## 🚀 Setup Instructions

Follow these steps to run the project locally:

**1. Clone the repository**
```bash
git clone https://github.com/sarthaksinghaniya/CM-Dashboard.git
cd CM-Dashboard
```

**2. Create a virtual environment**
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

**3. Install requirements**
```bash
pip install -r requirements.txt
```

**4. Setup Environment Variables**
Copy the example environment file and update it.
```bash
cd CM-Dasboard
cp .env.example .env
```

**5. Start the Server**
```bash
uvicorn app.main:app --reload
```

---

## 🧪 Testing & Execution

The system is built for easy verification:

**1. Run Pytests:**
```bash
# Set PYTHONPATH and execute pytest
$env:PYTHONPATH="./CM-Dasboard"; python -m pytest CM-Dasboard/tests/test_pipeline.py
```

**2. Run Evaluation Artifact Generation:**
```bash
python scripts/generate_eval_outputs.py
```
*Creates `metrics.json` and PNG plots in the `outputs/` folder.*

**3. Run End-to-End Mock Pipeline:**
```bash
python scripts/e2e_runner.py
```
*Traces a real complaint through the ML and RAG pipeline, saving the output to `outputs/results.json`.*

## 📚 API Documentation

Once the FastAPI server is running, you can access the Swagger documentation here:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)

## 📄 License
You are a senior systems engineer.

Build a deterministic, production-grade complaint processing ENGINE CORE.

Requirements:

* Implement a state machine:
  SUBMITTED → PROCESSING → RESOLVED | FAILED | FAILED_FINAL
* Add retry system:

  * retry_count (max 3)
  * exponential backoff
* Central pipeline executor:

  * idempotent
  * failure-safe
  * logs every transition
* Ensure:

  * no race conditions
  * thread-safe execution
  * no duplicate processing

Output:

* pipeline module
* state transition logic
* retry handler
* logging hooks

Do NOT include API routes.
Focus ONLY on core engine logic.

This project is licensed under the MIT License - see the LICENSE file for details.
