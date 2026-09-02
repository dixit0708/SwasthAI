import re

def refine_html():
    with open('frontend/index.html', 'r', encoding='utf-8') as f:
        html = f.read()
        
    # Remove eyebrows
    html = re.sub(r'<span class="eyebrow.*?>.*?</span>', '', html)
    
    # Update CTAs to avoid duplicate intent
    html = html.replace('>Explore Features<', '>See Capabilities<')
    
    # Final CTA section replacements
    html = html.replace('href="register.html" class="btn btn-white btn-lg">Get Started', 'href="register.html" class="btn btn-white btn-lg">Create Account')
    
    # Ensure fonts match
    html = html.replace('text-gradient', 'text-primary')
    
    with open('frontend/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
        
if __name__ == '__main__':
    refine_html()
