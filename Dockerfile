FROM python:3.11-slim

# Install OS packages needed for Tkinter and X11 forwarding
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      tk \
      python3-tk \
      libx11-6 \
      libxext6 \
      libxrender1 \
      libxft2 \
      libxinerama1 \
      libxcursor1 \
      libxi6 \
      libgl1 \
      libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy source
COPY logic.py gui.py .

# Default display will be provided at runtime via -e DISPLAY
ENV PYTHONUNBUFFERED=1

CMD ["python", "gui.py"]
