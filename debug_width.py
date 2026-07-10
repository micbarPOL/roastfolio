import json
from playwright.sync_api import sync_playwright
import os

# We need to run a local server first
import threading
import http.server
import socketserver

PORT = 8081
DIRECTORY = "/Users/michal.bardadyn/Documents/Code/Dash/investment-history/src"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

def start_server():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(f"http://localhost:{PORT}/index.html")
    
    # Wait for JS to run and data to "load" (liveDataReady event fires soon)
    page.wait_for_timeout(3000)
    
    # Switch to wallets tab manually
    page.evaluate("if (window.showTab) window.showTab('wallets');")
    page.wait_for_timeout(1000)
    
    # Run JS to find elements wider than viewport
    script = """
    () => {
        const bodyWidth = document.body.clientWidth;
        const windowWidth = window.innerWidth;
        const tooWide = [];
        
        // Check body scroll width vs inner width
        tooWide.push({
            tag: 'body',
            scrollWidth: document.body.scrollWidth,
            clientWidth: document.body.clientWidth,
            windowWidth: window.innerWidth
        });

        // Traverse all elements
        document.querySelectorAll('*').forEach(el => {
            const rect = el.getBoundingClientRect();
            // If the element extends past the right edge (considering x offset + width)
            // or if its calculated width is > 390
            if (rect.width > 390 || rect.right > 390) {
                // Ignore elements that are hidden or part of hidden tabs
                if (el.closest('.tab-content:not(.active)')) return;
                if (el.style.display === 'none') return;
                
                let classList = Array.from(el.classList).join('.');
                if (classList) classList = '.' + classList;
                let id = el.id ? '#' + el.id : '';
                
                tooWide.push({
                    element: el.tagName.toLowerCase() + id + classList,
                    width: rect.width,
                    right: rect.right,
                    left: rect.left
                });
            }
        });
        
        return tooWide;
    }
    """
    
    result = page.evaluate(script)
    print(json.dumps(result, indent=2))
    browser.close()
