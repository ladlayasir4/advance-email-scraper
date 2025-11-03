# advance-email-scraper
osint email scraper
# for linux Create an installation script install_shadow.sh

#!/bin/bash
echo "🔰 Installing Shadow Harvester on Kali Linux..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-pip python3-venv git tor torsocks \
    poppler-utils antiword xpdf-utils dnsutils whois proxychains4

# Create virtual environment
python3 -m venv shadow-env
source shadow-env/bin/activate

# Install Python packages
pip install --upgrade pip
pip install playwright aiohttp openpyxl python-docx pypdf2 dnspython \
    beautifulsoup4 requests requests[socks] urllib3 pandas lxml \
    aiohttp-socks socks pillow cryptography

# Install browsers
playwright install chromium
playwright install --with-deps chromium

# Start Tor
sudo systemctl start tor
sudo systemctl enable tor

echo "✅ Installation complete!"
echo "🚀 Activate environment: source shadow-env/bin/activate"
echo "🎯 Run tool: python3 shadow_harvester.py -t target.com"

# Make it executable and run:

bash
chmod +x install_shadow.sh
./install_shadow.sh

# shadow-harvester/
├── shadow_harvester.py
├── shadow-env/              # Virtual environment
├── install_shadow.sh        # Installation script



# for windows 
# Download from python.org or use chocolatey
choco install python -y
# Install chocolatey (if not installed)
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install required packages
choco install poppler git -y
# Create virtual environment
python -m venv shadow-env
shadow-env\Scripts\activate

# Install packages
pip install --upgrade pip
pip install playwright aiohttp openpyxl python-docx pypdf2 dnspython beautifulsoup4 requests requests[socks] urllib3 pandas lxml aiohttp-socks socks pillow cryptography

# Install Playwright browsers
playwright install chromium
# Using chocolatey
choco install tor -y

# Or download manually from torproject.org
# Start Tor service
tor
done 
