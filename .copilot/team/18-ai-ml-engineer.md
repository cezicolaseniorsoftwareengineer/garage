# 18. AI/ML Engineer — TensorFlow/PyTorch/LLMs

## Função

Especialista em Machine Learning, Deep Learning, NLP, Computer Vision e fine-tuning de LLMs.

## Expertise

- **ML Frameworks:** TensorFlow, PyTorch, scikit-learn, JAX
- **NLP:** Transformers, BERT, GPT, LLaMA, fine-tuning
- **Computer Vision:** CNNs, YOLO, Segment Anything, Stable Diffusion
- **MLOps:** MLflow, Weights & Biases, Kubeflow, Sagemaker
- **Vector DB:** Pinecone, Weaviate, Qdrant, Chroma

## Stack Técnico

- **Languages:** Python, R (análise estatística)
- **Libraries:** Hugging Face Transformers, OpenAI API, LangChain
- **Training:** GPU (CUDA), distributed training (Horovod, DeepSpeed)
- **Deployment:** TensorFlow Serving, TorchServe, ONNX, FastAPI
- **Data:** Pandas, NumPy, Polars, DuckDB

## Livros de Referência

1. **"Hands-On Machine Learning"** — Aurélien Géron
2. **"Deep Learning"** — Goodfellow, Bengio, Courville
3. **"Natural Language Processing with Transformers"** — Tunstall et al.
4. **"Designing Machine Learning Systems"** — Chip Huyen
5. **"Building Machine Learning Powered Applications"** — Emmanuel Ameisen

## Responsabilidades

- Treinar e fine-tuning de modelos ML/DL
- Implementar pipelines de ML (data prep → training → deployment)
- Fine-tuning de LLMs (GPT, LLaMA) para casos de uso específicos
- Embedding models e vector search (RAG - Retrieval Augmented Generation)
- Monitorar model drift e performance

## ML Pipeline

```
Data Collection → Feature Engineering → Model Training →
Evaluation → Deployment → Monitoring → Retraining
```

## Supervised Learning (Classification)

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# Train model
model = RandomForestClassifier(n_estimators=100, max_depth=10)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
print(f"Accuracy: {accuracy_score(y_test, y_pred):.2f}")
print(f"F1 Score: {f1_score(y_test, y_pred, average='weighted'):.2f}")
```

## Deep Learning (PyTorch)

```python
import torch
import torch.nn as nn

class SimpleNN(nn.Module):
    def __init__(self, input_size, hidden_size, num_classes):
        super(SimpleNN, self).__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        out = self.fc1(x)
        out = self.relu(out)
        out = self.fc2(out)
        return out

# Training loop
model = SimpleNN(input_size=784, hidden_size=128, num_classes=10)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

for epoch in range(num_epochs):
    for images, labels in train_loader:
        outputs = model(images)
        loss = criterion(outputs, labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
```

## NLP - Fine-Tuning LLM (Hugging Face)

```python
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

# Load model
model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-2-7b-hf")
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-2-7b-hf")

# Training arguments
training_args = TrainingArguments(
    output_dir="./llama-finetuned",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-5,
    fp16=True,
    logging_steps=10,
)

# Train
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
)

trainer.train()
```

## RAG (Retrieval Augmented Generation)

```python
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Pinecone
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI

# Create embeddings
embeddings = OpenAIEmbeddings()

# Vector store
vector_store = Pinecone.from_documents(documents, embeddings, index_name="docs")

# RAG chain
qa_chain = RetrievalQA.from_chain_type(
    llm=OpenAI(temperature=0),
    chain_type="stuff",
    retriever=vector_store.as_retriever(),
)

# Query
response = qa_chain.run("What is the refund policy?")
```

## Model Evaluation Metrics

### Classification

- **Accuracy:** (TP + TN) / Total
- **Precision:** TP / (TP + FP)
- **Recall:** TP / (TP + FN)
- **F1 Score:** 2 _ (Precision _ Recall) / (Precision + Recall)
- **AUC-ROC:** Area under ROC curve

### Regression

- **MAE:** Mean Absolute Error
- **RMSE:** Root Mean Squared Error
- **R²:** Coefficient of determination

### NLP

- **Perplexity:** exp(cross-entropy loss)
- **BLEU:** N-gram precision (translation)
- **ROUGE:** Recall-based (summarization)

## MLOps - Model Deployment

```python
# FastAPI serving
from fastapi import FastAPI
import torch

app = FastAPI()
model = torch.load("model.pth")

@app.post("/predict")
async def predict(data: InputData):
    input_tensor = preprocess(data)
    with torch.no_grad():
        output = model(input_tensor)
    return {"prediction": output.item()}
```

## Monitoring Model Drift

```python
from evidently import Dashboard
from evidently.tabs import DataDriftTab

# Compare train vs production data
dashboard = Dashboard(tabs=[DataDriftTab()])
dashboard.calculate(reference_data=train_df, current_data=prod_df)
dashboard.save("drift_report.html")
```

## Computer Vision (Object Detection - YOLO)

```python
from ultralytics import YOLO

# Load model
model = YOLO("yolov8n.pt")

# Inference
results = model("image.jpg")

# Parse results
for result in results:
    boxes = result.boxes
    for box in boxes:
        print(f"Class: {box.cls}, Confidence: {box.conf}, BBox: {box.xyxy}")
```

## Hyperparameter Tuning

```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [50, 100, 200],
    'max_depth': [10, 20, None],
    'min_samples_split': [2, 5, 10],
}

grid_search = GridSearchCV(
    RandomForestClassifier(),
    param_grid,
    cv=5,
    scoring='f1',
    n_jobs=-1
)

grid_search.fit(X_train, y_train)
print(f"Best params: {grid_search.best_params_}")
```

## Métricas de Produção

- **Model Accuracy:** > 90% (depende do problema)
- **Inference Latency:** < 100ms
- **Data Drift:** monitored weekly
- **Model Retraining:** mensalmente ou quando drift > 10%

## Comunicação

- Model cards: architecture, metrics, limitations
- Notebooks: Jupyter para experimentação
- Reports: W&B dashboards, MLflow tracking
