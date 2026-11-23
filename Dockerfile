FROM python:3.11-slim

# Tao user non-root theo chuan Hugging Face Spaces (UID 1000)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    ENV=production

WORKDIR $HOME/app

# Cai dat dependencies
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy ma nguon ung dung
COPY --chown=user:user . .

# Hugging Face Spaces mac dinh mo port 7860
EXPOSE 7860

CMD ["python", "-m", "tiebreak_engine.playground.run_playground"]
