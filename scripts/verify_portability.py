"""Install the archive's source into an isolated temporary directory and test fresh DB initialization."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from package_project import ROOT, project_files


def main():
    workspace = ROOT.parent.resolve()
    temporary = Path(tempfile.mkdtemp(prefix='warhammer-portability-', dir=workspace)).resolve()
    assert temporary.is_relative_to(workspace) and temporary != workspace
    try:
        target = temporary / 'WarhammerAI'
        for source, relative in project_files():
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        shutil.copy2(target / '.env.example', target / '.env')
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        for key in ['DJANGO_SECRET_KEY', 'DJANGO_DEBUG', 'DJANGO_ALLOWED_HOSTS', 'RECOMMENDATIONS_URL', 'RECOMMENDATIONS_API_KEY']:
            env.pop(key, None)
        def run(args):
            process = subprocess.run([sys.executable] + args, cwd=target, env=env, capture_output=True, text=True, encoding='utf-8')
            if process.returncode:
                raise RuntimeError(process.stdout[-2000:] + process.stderr[-2000:])
            return process.stdout
        run(['manage.py', 'migrate', '--noinput'])
        run(['manage.py', 'seed_demo'])
        again = run(['manage.py', 'seed_demo'])
        assert 'added: 0' in again
        program = '''import os,json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','warhammer_project.settings')
import django;django.setup()
from django.test import Client
from store.models import Product,CartItem
from pathlib import Path
c=Client()
assert c.get('/').status_code==200
assert len(c.get('/api/v1/products/').json())==15
assert all((Path('media')/p.image.name).is_file() for p in Product.objects.all())
r=c.post('/api/v1/auth/login/',data=json.dumps({'username':'demo','password':'WarhammerDemo2026!'}),content_type='application/json')
assert r.status_code==200
c.defaults['HTTP_AUTHORIZATION']='Token '+r.json()['token']
p=Product.objects.get(name='Гвардия Ворона')
assert c.post('/api/v1/cart/',data=json.dumps({'product_id':p.pk,'quantity':1}),content_type='application/json').status_code==201
assert c.get('/api/v1/cart/').json()['total_price']=='2250.00'
r=c.post('/api/v1/orders/',data='{}',content_type='application/json')
assert r.status_code==201 and len(r.json()['items'])==1
assert CartItem.objects.count()==0
assert c.get('/api/schema/').status_code==200
print('Clean source, empty .env template, migrations, seed, auth, images, cart and order: OK')
'''
        result = run(['-c', program])
        evidence = {'passed': True, 'verified_at': datetime.now(timezone.utc).isoformat(),
                    'checks': ['fresh SQLite database', 'only .env.example values', '15 products', 'idempotent seed',
                               'all local image files', 'token login', 'cart discount 2250.00', 'persistent order', 'OpenAPI'],
                    'runtime': sys.version.split()[0], 'reused_dependencies': True}
        (ROOT / 'docs/portability_validation.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        print(result.strip())
    finally:
        # The target is a task-owned generated directory, checked before recursive removal.
        assert temporary.is_relative_to(workspace) and temporary.name.startswith('warhammer-portability-')
        shutil.rmtree(temporary)


if __name__ == '__main__':
    main()
