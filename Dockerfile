# --- STAGE 1: The "Builder" ---
FROM python:3.11-slim as builder

RUN apt-get update && apt-get install -y build-essential cmake
WORKDIR /wheels
COPY requirements.txt .
RUN pip wheel --no-cache-dir -r requirements.txt


# --- STAGE 2: The "Final Image" ---
FROM python:3.11-slim

RUN apt-get update && apt-get install -y libsm6 libxext6 && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY --from=builder /wheels /wheels

# --- THE FIX IS HERE ---
# Remove the requirements.txt file before installing, as it's not a package
RUN rm /wheels/requirements.txt

# Install the packages from the local files.
RUN pip install --no-cache-dir /wheels/*

# Now, copy our application code into the final image
COPY . .

EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]