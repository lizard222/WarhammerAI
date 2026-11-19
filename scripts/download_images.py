"""Download local product photographs and retain their source pages."""
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SHOP = 'https://www.wargamesemporium.co.uk'
QUERIES = {
    'intercessors': 'intercessor squad', 'orks': 'ork boyz', 'aeldari': 'aeldari guardians',
    'necrons': 'necron warriors', 'starter': 'warhammer starter set', 'introductory': 'warhammer introductory set',
    'paints': 'paints tools set', 'blue': 'macragge blue', 'black': 'abaddon black',
    'brush': 'base brush medium', 'dice': 'space marines dice', 'book': '40,000 core',
}


def read_url(url):
    with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as response:
        return response.read()


def download(pair):
    slug, query = pair
    params = urlencode({'q': query, 'resources[type]': 'product', 'resources[limit]': '5'})
    result = json.loads(read_url(SHOP + '/search/suggest.json?' + params))
    products = result.get('resources', {}).get('results', {}).get('products', [])
    if not products:
        raise RuntimeError('No image found for ' + slug)
    product = products[0]
    image_url = product.get('image') or product.get('featured_image', {}).get('url')
    if isinstance(image_url, dict):
        image_url = image_url.get('url')
    if not image_url:
        raise RuntimeError('Image missing for ' + slug)
    if image_url.startswith('//'):
        image_url = 'https:' + image_url
    image = Image.open(io.BytesIO(read_url(image_url))).convert('RGB')
    image.thumbnail((900, 900))
    path = ROOT / 'media/products' / (slug + '.jpg')
    image.save(path, quality=88, optimize=True)
    page = product.get('url', '/products/' + product.get('handle', ''))
    if page.startswith('/'):
        page = SHOP + page
    return slug, {'title': product['title'], 'page': page, 'image_url': image_url, 'file': 'products/' + path.name,
                  'note': 'Фотография товара для учебной демонстрации. Права принадлежат правообладателям.'}


if __name__ == '__main__':
    results = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {slug: pool.submit(download, (slug, query)) for slug, query in QUERIES.items()}
        for slug, future in futures.items():
            try:
                key, source = future.result()
                results[key] = source
                print(key + ': ' + source['title'])
            except Exception as exc:
                print(slug + ': ' + str(exc))
    (ROOT / 'docs/image_sources.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Downloaded:', len(results))
