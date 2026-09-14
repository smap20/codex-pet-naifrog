#!/usr/bin/env python3
"""Offline Linux and macOS installer. Python 3.8+ standard library only."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import uuid

BUNDLE = Path(__file__).resolve().parent

# Every build is pinned to both the whole ASAR and the two patched members. A
# new Codex release therefore fails closed until its minified symbols and
# anchors have been reviewed. The Linux constants remain for v4.4 state
# compatibility and for scripts which imported them from earlier releases.
VERSION = '26.903.61454'
ORIGINAL = '43d2e0e6d8cc1796a675f769c04f09038cdb0d1922ad358f852027979e9bd8ff'
PREVIOUS = 'c6f78ad4dd35b8429b07bc258f5b45e1990982d93fed72242ecc1e7766d14dff'
PATCHED = 'f0b6db965d022705f85fadec54296f6cdb3e2293f748230d260c278b6a176d5e'

BUILD_SPECS = [
    {
        'id': 'linux-26.903.61454', 'platform': 'linux', 'version': VERSION,
        'original': ORIGINAL, 'previous': PREVIOUS, 'patched': PATCHED,
        'members': {
            '.vite/build/src-J2PvP4xj.js': '4cc980cd737b02f999b9fe8d9757c37d2ce86c928043f19f46d56cc52bce8f66',
            'webview/assets/app-initial-5738ed8d0dba.js': '2a200058c034d70daeb6874c40e8b708879dd1060c9419c6271d91b0bfdc818f',
        },
        'loader_member': '.vite/build/src-J2PvP4xj.js',
        'ui_member': 'webview/assets/app-initial-5738ed8d0dba.js',
        'loader_function': 'e0', 'safe_join': 't0', 'file_api': 'X', 'image_info': 'r0',
        'sprite_rows': 'ver', 'renderer': 'qer', 'react': 'Ger',
        'reduced_motion': 'VLe', 'classnames': 'K', 'pet_styles': 'Uer',
        'next_function': 'Yer',
    },
    {
        'id': 'macos-26.903.71938', 'platform': 'darwin', 'version': '26.903.71938',
        'original': '58fef82480b9064e209b5b2fd934992e8d71515aea8084482369cfeaff1b8ee0',
        'previous': None,
        'patched': '46318beb84f148f0de87640dfc8d28f842780bcddf7acdedf8a02ce32eaf910a',
        'members': {
            '.vite/build/src-B6LqG3ek.js': '9a1d9737c526cbba0e18e5ffc3b9371ef055318e7eabb7584b082fbcdb24472e',
            'webview/assets/app-initial-a9514281e192.js': '038d28242240bb19fd90c7a380d80c6d23caaebc77a3ebb87ff6045bc49762c6',
        },
        'loader_member': '.vite/build/src-B6LqG3ek.js',
        'ui_member': 'webview/assets/app-initial-a9514281e192.js',
        'loader_function': 'e0', 'safe_join': 't0', 'file_api': 'X', 'image_info': 'r0',
        'sprite_rows': 'Y9n', 'renderer': 'wer', 'react': 'Ser',
        'reduced_motion': 'BLe', 'classnames': 'K', 'pet_styles': 'ber',
        'next_function': 'Eer',
    },
    {
        'id': 'macos-26.908.31748', 'platform': 'darwin', 'version': '26.908.31748',
        'original': 'c388f239a8e8e6af18612fad04f3b89456ea3d731e0ecaecc42ea389ddc269d6',
        'previous': None,
        'patched': '6dfe234bd2851ecdd43d93b2fbc1a149d8ac6e899aed05a555cd43c98a7c8e95',
        'members': {
            '.vite/build/src-CCXHtyvY.js': 'a42da38cbb14b28399f1d54fcf453bffc5e9802663e7e098f187c8378f4c7a40',
            'webview/assets/app-initial-c932b6b5121b.js': '13e51e004d7cc692aed4c401621f83993b1d21b6de763aca44b4e59c1693a0d6',
        },
        'loader_member': '.vite/build/src-CCXHtyvY.js',
        'ui_member': 'webview/assets/app-initial-c932b6b5121b.js',
        'loader_function': 'p2', 'safe_join': 'm2', 'file_api': 'X', 'image_info': 'g2',
        'sprite_rows': 'Fco', 'renderer': 'plo', 'react': 'dlo',
        'reduced_motion': 'YJe', 'classnames': 'S', 'pet_styles': 'llo',
        'next_function': 'hlo',
    },
]


# macOS adapters remain available for future porting, but latest question hooks
# have only been verified against the Linux build.
MACOS_ADAPTERS = [x for x in BUILD_SPECS if x['platform'] == 'darwin']
BUILD_SPECS = [x for x in BUILD_SPECS if x['platform'] == 'linux']
BUILD_SPECS[0]['previous'] = None
BUILD_SPECS[0]['patched'] = 'd3fa96178adc15ac1e8add704e9c5e9b96bcf3a89bb1993fc8872ceffb87ac15'
BUILD_SPECS[0]['members'].update(json.loads((BUNDLE / 'runtime/extra-members.json').read_text()))

class InstallError(Exception):
    pass


def require(ok, message):
    if not ok:
        raise InstallError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    stage = path.with_name(path.name + '.stage')
    stage.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(stage, path)


def verify_bundle():
    index = json.loads((BUNDLE / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    for name, expected in index.items():
        rel = Path(name)
        require(not rel.is_absolute() and '..' not in rel.parts, '包校验表路径无效。')
        path = BUNDLE / rel
        require(path.is_file() and not path.is_symlink() and sha(path) == expected,
                '安装包文件缺失或损坏：' + name)
    return index


class Asar:
    def __init__(self, path):
        self.path = Path(path)
        with self.path.open('rb') as stream:
            first = stream.read(16)
            require(len(first) == 16, '无效的 app.asar。')
            values = struct.unpack('<4I', first)
            require(values[0] == 4 and 0 < values[3] < 32 * 1024 * 1024,
                    '不支持的 ASAR 文件头。')
            self.header_bytes = stream.read(values[3])
            self.header = json.loads(self.header_bytes)
            self.base = 8 + values[1]
        self.entries = []

        def walk(node, prefix=''):
            for name, item in node['files'].items():
                member = prefix + name
                if 'files' in item:
                    walk(item, member + '/')
                elif 'offset' in item and not item.get('unpacked'):
                    self.entries.append((member, item, int(item['offset']), item['size']))
        walk(self.header)

    def read(self, member):
        for name, _, offset, size in self.entries:
            if name == member:
                with self.path.open('rb') as stream:
                    stream.seek(self.base + offset)
                    data = stream.read(size)
                require(len(data) == size, '归档成员不完整：' + member)
                return data
        raise InstallError('归档缺少成员：' + member)


def asar_header_sha(path):
    return hashlib.sha256(Asar(path).header_bytes).hexdigest()


def once(text, old, new):
    require(text.count(old) == 1, '播放器代码与受支持版本不一致；没有修改文件。')
    return text.replace(old, new)


def render_runtime(filename, spec):
    text = (BUNDLE / 'runtime' / filename).read_text(encoding='utf-8')
    values = {
        '__NF_SAFE_JOIN__': spec['safe_join'],
        '__NF_FS__': spec['file_api'],
        '__NF_IMAGE_INFO__': spec['image_info'],
        '__NF_REACT__': spec['react'],
        '__NF_REDUCED_MOTION__': spec['reduced_motion'],
        '__NF_CLASSNAMES__': spec['classnames'],
        '__NF_PET_STYLES__': spec['pet_styles'],
    }
    for placeholder, value in values.items():
        text = text.replace(placeholder, value)
    require('__NF_' not in text, '运行时代码包含未替换的构建占位符。')
    return text


def patch_members(archive, spec, archive_digest=None):
    digest = archive_digest or sha(archive.path)
    originals = {name: archive.read(name) for name in spec['members']}
    if spec.get('previous') and digest == spec['previous']:
        result = {}
        for member, filename in [(spec['loader_member'], 'animation-loader.js'),
                                 (spec['ui_member'], 'animation-runtime.js')]:
            before = (BUNDLE / 'runtime' / ('v4.4-' + filename)).read_text(encoding='utf-8')
            after = render_runtime(filename, spec)
            result[member] = once(originals[member].decode(), before, after).encode()
        return result
    for name, data in originals.items():
        require(hashlib.sha256(data).hexdigest() == spec['members'][name],
                '代码指纹不匹配：' + name)

    loader = originals[spec['loader_member']].decode()
    loader = once(loader, 'spritesheetPath:H().trim().min(1).default(`spritesheet.webp`)',
                  'animationManifestPath:H().trim().min(1).optional(),spritesheetPath:H().trim().min(1).default(`spritesheet.webp`)')
    loader = once(loader, 'spriteVersionNumber:n.data.spriteVersionNumber,spritesheetDataUrl:l.spritesheetDataUrl',
                  'spriteVersionNumber:n.data.spriteVersionNumber,spritesheetDataUrl:l.spritesheetDataUrl,animationSpec:await nfReadAnimation(e,t,a,n.data.animationManifestPath)')
    function_anchor = 'async function ' + spec['loader_function'] + '('
    loader = once(loader, function_anchor,
                  render_runtime('animation-loader.js', spec) + '\n' + function_anchor)

    ui = originals[spec['ui_member']].decode()
    source = ('petId:e.id,spriteRowCount:' + spec['sprite_rows'] +
              '(e.spriteVersionNumber),spritesheetUrl:e.spritesheetUrl')
    ui = once(ui, source, source + ',animationSpec:e.animationSpec')
    custom = 'spritesheetUrl:e.spritesheetDataUrl,upgradeDirectoryPath:t<2?e.directoryPath:void 0'
    ui = once(ui, custom,
              'spritesheetUrl:e.spritesheetDataUrl,animationSpec:e.animationSpec,upgradeDirectoryPath:t<2?e.directoryPath:void 0')
    tail = '},"aria-hidden":`true`})}}));function ' + spec['next_function'] + '('
    wrapper = ('},"aria-hidden":`true`})};const nfOriginal=' + spec['renderer'] + ';' +
               spec['renderer'] + '=props=>props.source?.animationSpec?' + spec['react'] +
               '.createElement(nfPetRenderer,props):' + spec['react'] +
               '.createElement(nfOriginal,props)}));\n' +
               render_runtime('input-bridge.js', spec) + '\n' + render_runtime('animation-runtime.js', spec) + '\nfunction ' +
               spec['next_function'] + '(')
    ui = once(ui, tail, wrapper)
    hooks = json.loads((BUNDLE / 'runtime/question-hooks.json').read_text())
    for before, after in hooks.items():
        ui = once(ui, before, after)
    result = {spec['loader_member']: loader.encode(), spec['ui_member']: ui.encode()}
    for member, before, after in [
        ('webview/assets/avatar-mascot-button-f61a6e3fe6ad.js', 'ne?`jumping`:u', 'ne?(s.animationSpec?`waving`:`jumping`):u'),
        ('webview/assets/profile-720b5ad88b98.js', 'let l=r?`jumping`:`idle`', 'let l=r?(c.animationSpec?`waving`:`jumping`):`idle`')]:
        result[member] = once(originals[member].decode(), before, after).encode()
    return result


def build_archive(source, destination, spec, verify_result=True):
    digest = sha(source)
    allowed = [spec['original']]
    if spec.get('previous'):
        allowed.append(spec['previous'])
    require(digest in allowed, '原始 App 指纹不匹配。')
    archive = Asar(source)
    mods = patch_members(archive, spec, digest)
    header = copy.deepcopy(archive.header)
    entries = []

    def walk(node, prefix=''):
        for name, item in node['files'].items():
            member = prefix + name
            if 'files' in item:
                walk(item, member + '/')
            elif 'offset' in item and not item.get('unpacked'):
                entries.append((member, item, int(item['offset']), item['size']))
    walk(header)

    offset = 0
    for name, item, _, _ in entries:
        if name in mods:
            data = mods[name]
            item['size'] = len(data)
            block_size = item.get('integrity', {}).get('blockSize', 4194304)
            item['integrity'] = {
                'algorithm': 'SHA256', 'hash': hashlib.sha256(data).hexdigest(),
                'blockSize': block_size,
                'blocks': [hashlib.sha256(data[i:i + block_size]).hexdigest()
                           for i in range(0, len(data), block_size)],
            }
        item['offset'] = str(offset)
        offset += item['size']

    raw = json.dumps(header, separators=(',', ':'), ensure_ascii=False).encode()
    payload = struct.pack('<I', len(raw)) + raw
    payload += b'\0' * ((-len(payload)) % 4)
    pickle = struct.pack('<I', len(payload)) + payload
    with Path(source).open('rb') as src, Path(destination).open('wb') as dst:
        dst.write(struct.pack('<II', 4, len(pickle)) + pickle)
        for name, _, old_offset, size in entries:
            if name in mods:
                dst.write(mods[name])
            else:
                src.seek(archive.base + old_offset)
                remaining = size
                while remaining:
                    block = src.read(min(1024 * 1024, remaining))
                    require(bool(block), '读取原始归档失败。')
                    dst.write(block)
                    remaining -= len(block)
    if verify_result:
        require(sha(destination) == spec['patched'],
                '重建结果与已验证播放器不一致；不会安装。')


def platform_key(value=None):
    value = value or sys.platform
    if value.startswith('linux'):
        return 'linux'
    if value == 'darwin':
        return 'darwin'
    return value


def spec_for(version, digest, platform=None):
    key = platform_key(platform)
    for spec in BUILD_SPECS:
        fingerprints = [spec['original'], spec['patched']]
        if spec.get('previous'):
            fingerprints.append(spec['previous'])
        if spec['platform'] == key and spec['version'] == version and digest in fingerprints:
            return spec
    return None


def mac_bundle_for_asar(app):
    app = Path(app)
    require(app.name == 'app.asar' and app.parent.name == 'Resources' and
            app.parent.parent.name == 'Contents' and app.parent.parent.parent.suffix == '.app',
            'macOS 安装源必须是 .app/Contents/Resources/app.asar。')
    return app.parent.parent.parent


def app_asar(path):
    path = Path(path).expanduser()
    if path.is_dir() and path.suffix == '.app':
        return (path / 'Contents/Resources/app.asar').resolve()
    return path.resolve()


def inspect(app, platform=None):
    app = Path(app).resolve()
    archive = Asar(app)
    metadata = json.loads(archive.read('package.json'))
    digest = sha(app)
    key = platform_key(platform)
    spec = spec_for(metadata.get('version'), digest, key)
    supported_versions = sorted(
        {item['version'] for item in BUILD_SPECS if item['platform'] == key})
    result = {
        'app': str(app), 'platform': key, 'version': metadata.get('version'),
        'sha256': digest,
        'supported': metadata.get('name') == 'openai-codex-electron' and spec is not None,
        'alreadyPatched': bool(spec and digest == spec['patched']),
        'supportedVersions': supported_versions,
    }
    if spec:
        result['build'] = spec['id']
    if key == 'darwin':
        result['sourceBundle'] = str(mac_bundle_for_asar(app))
        result['installMode'] = 'side-by-side'
    return result


def discover(explicit, platform=None):
    key = platform_key(platform)
    if explicit:
        path = app_asar(explicit)
        require(path.is_file(), '找不到指定的 app.asar：' + str(path))
        if key == 'darwin':
            mac_bundle_for_asar(path)
        return path
    if key == 'darwin':
        bundles = [Path('/Applications/ChatGPT.app'), Path('/Applications/Codex.app'),
                   Path.home() / 'Applications/ChatGPT.app', Path.home() / 'Applications/Codex.app']
        supported = []
        for bundle in bundles:
            path = bundle / 'Contents/Resources/app.asar'
            if path.is_file():
                try:
                    report = inspect(path, key)
                    if report['supported'] and not report['alreadyPatched']:
                        supported.append((tuple(int(x) for x in report['version'].split('.')), path.resolve()))
                except (InstallError, OSError, ValueError, json.JSONDecodeError):
                    pass
        require(bool(supported),
                '未找到受支持的 ChatGPT/Codex App。请加 --app "/Applications/ChatGPT.app" 指定。')
        return sorted(supported, key=lambda item: item[0], reverse=True)[0][1]
    require(key == 'linux', '本安装器仅支持 Linux 和 macOS。')
    candidates = [Path(path) for path in [
        '/usr/lib/chatgpt/resources/app.asar', '/opt/Codex/resources/app.asar',
        '/opt/codex/resources/app.asar', '/usr/lib/codex/resources/app.asar']]
    for root in [Path('/opt'), Path.home() / '.local/share', Path.home() / 'Applications']:
        if root.is_dir():
            candidates.extend(root.glob('*[Cc]odex*/resources/app.asar'))
            candidates.extend(root.glob('*[Cc]hatgpt*/resources/app.asar'))
    found = sorted(set(path.resolve() for path in candidates if path.is_file()))
    require(len(found) == 1,
            '未找到唯一的 Codex App。请加 --app /实际路径/resources/app.asar 指定。候选：' + str(found))
    return found[0]


def tree_hashes(folder):
    result = {}
    if not folder.exists():
        return result
    require(folder.is_dir() and not folder.is_symlink(), '宠物目录不能是符号链接：' + str(folder))
    for path in sorted(folder.rglob('*')):
        require(not path.is_symlink(), '宠物目录包含符号链接，请先单独备份处理：' + str(path))
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = sha(path)
    return result


def replace_app(source, target, expected):
    require(sha(target) == expected, 'App 在操作期间已变化；拒绝覆盖。')
    stage = target.with_name('app.asar.naifrog-' + uuid.uuid4().hex + '.stage')
    try:
        if os.access(target.parent, os.W_OK):
            shutil.copyfile(source, stage)
            os.chmod(stage, target.stat().st_mode & 0o777)
            require(sha(stage) == sha(source), 'App 暂存校验失败。')
            require(sha(target) == expected, 'App 在操作期间已变化；拒绝覆盖。')
            os.replace(stage, target)
        else:
            require(shutil.which('sudo') is not None, '写入 App 需要 sudo，但系统没有 sudo。')
            print('写入应用目录需要管理员权限；sudo 可能请求你的 Linux 密码。', flush=True)
            subprocess.run(['sudo', 'install', '-m', '644', str(source), str(stage)], check=True)
            require(sha(stage) == sha(source) and sha(target) == expected,
                    'App 暂存或原文件校验失败。')
            subprocess.run(['sudo', 'mv', '-f', str(stage), str(target)], check=True)
    finally:
        if stage.exists():
            if os.access(stage.parent, os.W_OK):
                stage.unlink()
            else:
                subprocess.run(['sudo', '-n', 'rm', '-f', str(stage)], check=False)


def prepare_pet(home):
    pet = home / 'pets/naifrog'
    desired = tree_hashes(BUNDLE / 'pet')
    original = tree_hashes(pet)
    return pet, desired, original, pet.exists()


def install_linux(app, home):
    info = inspect(app, 'linux')
    require(info['supported'],
            '不支持这个 Codex 构建；没有修改 App 或宠物。受支持版本：' +
            ', '.join(info['supportedVersions']) + '（还需代码指纹匹配）。')
    spec = next(item for item in BUILD_SPECS if item['id'] == info['build'])
    pet, desired, original_pet, had_pet = prepare_pet(home)
    state_root = home / 'naifrog-installer'
    state_file = state_root / 'installed.json'
    prior_state = None
    if state_file.exists():
        previous = json.loads(state_file.read_text(encoding='utf-8'))
        require(previous.get('status') in ['installed', 'uninstalled'],
                '上次安装未结束，请按记录恢复：' + str(state_file))
        if previous['status'] == 'installed':
            require(previous.get('mode', 'linux-in-place') == 'linux-in-place' and
                    previous['app'] == str(app) and previous['pet'] == str(pet),
                    '上次安装使用了其他路径；请先卸载该次安装。')
            if info['sha256'] == spec['patched'] and tree_hashes(pet) == desired:
                print('已安装同一版奶蛙 v4.6.1，无需重复操作。')
                return previous
            require(previous.get('revision') == 'v4.4' and info['sha256'] == spec.get('previous') and
                    tree_hashes(pet) == previous['installedPetFiles'],
                    '安装后的 App 或宠物已改变；请保留现状并检查 installed.json。')
            prior_state = previous
    state_root.mkdir(parents=True, exist_ok=True)
    backup = state_root / ('backup-' + time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    backup.mkdir()
    shutil.copy2(app, backup / 'app.asar')
    require(sha(backup / 'app.asar') == info['sha256'], 'App 备份校验失败。')
    if had_pet:
        shutil.copytree(pet, backup / 'pet')
        require(tree_hashes(backup / 'pet') == original_pet, '宠物备份校验失败。')
    pet.parent.mkdir(parents=True, exist_ok=True)
    stage = pet.with_name('naifrog-stage-' + uuid.uuid4().hex)
    displaced = pet.with_name('naifrog-previous-' + uuid.uuid4().hex)
    record = {
        'status': 'prepared', 'mode': 'linux-in-place', 'revision': 'v4.6.1',
        'build': spec['id'], 'app': str(app), 'pet': str(pet), 'backup': str(backup),
        'beforeAppSha256': info['sha256'], 'installedAppSha256': spec['patched'],
        'hadPet': had_pet, 'beforePetFiles': original_pet, 'installedPetFiles': desired,
        'restartRequired': True,
    }
    if prior_state:
        record['previousInstallation'] = prior_state
    app_changed = False
    pet_changed = False
    write_json(state_file, record)
    try:
        shutil.copytree(BUNDLE / 'pet', stage)
        require(tree_hashes(stage) == desired, '宠物暂存校验失败。')
        if info['sha256'] != spec['patched']:
            print('正在本地生成完整动画播放器扩展…', flush=True)
            build_archive(backup / 'app.asar', backup / 'patched.asar', spec)
            replace_app(backup / 'patched.asar', app, info['sha256'])
            app_changed = True
        require(sha(app) == spec['patched'] and tree_hashes(pet) == original_pet,
                '目标在安装期间改变；拒绝继续。')
        if had_pet:
            os.replace(pet, displaced)
        os.replace(stage, pet)
        pet_changed = True
        require(tree_hashes(pet) == desired, '宠物安装后校验失败。')
        record['status'] = 'installed'
        write_json(state_file, record)
    except BaseException:
        if pet_changed and pet.exists():
            require(tree_hashes(pet) == desired,
                    '回滚前发现宠物被其他程序改变，请使用备份手动恢复：' + str(backup))
            shutil.rmtree(pet)
        if displaced.exists():
            os.replace(displaced, pet)
        if app_changed:
            replace_app(backup / 'app.asar', app, spec['patched'])
        record['status'] = 'uninstalled'
        write_json(state_file, prior_state or record)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    if displaced.exists():
        shutil.rmtree(displaced)
    if (backup / 'patched.asar').exists():
        (backup / 'patched.asar').unlink()
    print('安装完成：' + str(pet))
    print('备份：' + str(backup))
    print('请完全退出并重新打开 Codex，再在宠物列表选择“奶蛙”。')
    return record


def clone_app(source, destination):
    require(not destination.exists(), '暂存 App 路径已存在：' + str(destination))
    ditto = Path('/usr/bin/ditto')
    if ditto.is_file():
        subprocess.run([str(ditto), '--rsrc', '--extattr', str(source), str(destination)], check=True)
    else:
        shutil.copytree(source, destination, symlinks=True, copy_function=shutil.copy2)


def update_mac_integrity(bundle, display_name=None):
    plist_path = bundle / 'Contents/Info.plist'
    require(plist_path.is_file() and not plist_path.is_symlink(), 'App 缺少有效的 Info.plist。')
    with plist_path.open('rb') as stream:
        plist = plistlib.load(stream)
    integrity = plist.get('ElectronAsarIntegrity')
    require(isinstance(integrity, dict) and isinstance(integrity.get('Resources/app.asar'), dict),
            'App 缺少 Electron ASAR 完整性配置。')
    app = bundle / 'Contents/Resources/app.asar'
    integrity['Resources/app.asar']['hash'] = asar_header_sha(app)
    if display_name:
        plist['CFBundleDisplayName'] = display_name
    stage = plist_path.with_name('Info.plist.naifrog-stage')
    with stage.open('wb') as stream:
        plistlib.dump(plist, stream, fmt=plistlib.FMT_XML, sort_keys=False)
    os.replace(stage, plist_path)
    return integrity['Resources/app.asar']['hash']


def sign_mac_bundle(bundle):
    codesign = Path('/usr/bin/codesign')
    require(codesign.is_file(), '系统缺少 codesign，无法安全生成 macOS App。')
    subprocess.run([str(codesign), '--force', '--deep', '--sign', '-',
                    '--preserve-metadata=identifier,entitlements,flags,runtime', str(bundle)], check=True)
    subprocess.run([str(codesign), '--verify', '--deep', '--strict', str(bundle)], check=True)


def verify_mac_bundle(bundle, expected_asar, expected_integrity=None, verify_signature=True):
    require(bundle.is_dir() and not bundle.is_symlink(),
            '奶蛙 App 不存在或不是普通目录：' + str(bundle))
    app = bundle / 'Contents/Resources/app.asar'
    require(app.is_file() and sha(app) == expected_asar, '奶蛙 App 的播放器已改变。')
    plist_path = bundle / 'Contents/Info.plist'
    with plist_path.open('rb') as stream:
        plist = plistlib.load(stream)
    actual = plist.get('ElectronAsarIntegrity', {}).get('Resources/app.asar', {}).get('hash')
    required = expected_integrity or asar_header_sha(app)
    require(actual == required == asar_header_sha(app), '奶蛙 App 的 ASAR 完整性记录不匹配。')
    if verify_signature:
        result = subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(bundle)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        require(result.returncode == 0, '奶蛙 App 的签名已改变：' + result.stderr.strip())
    return True


def mac_target_path(source_bundle, explicit=None):
    if explicit:
        target = Path(explicit).expanduser().absolute()
    else:
        target = (Path.home() / 'Applications' /
                  (source_bundle.stem + ' Naifrog.app')).absolute()
    require(target.suffix == '.app', '--target-app 必须以 .app 结尾。')
    require(target != source_bundle.absolute(), '目标不能覆盖官方 App；请选择另一个 --target-app。')
    return target


def install_macos(app, home, target_app=None):
    info = inspect(app, 'darwin')
    require(info['supported'] and not info['alreadyPatched'],
            '不支持这个 macOS 构建；没有修改 App 或宠物。受支持版本：' +
            ', '.join(info['supportedVersions']) + '（还需代码指纹匹配）。')
    spec = next(item for item in BUILD_SPECS if item['id'] == info['build'])
    source_bundle = mac_bundle_for_asar(app)
    target = mac_target_path(source_bundle, target_app)
    pet, desired, original_pet, had_pet = prepare_pet(home)
    state_root = home / 'naifrog-installer'
    state_file = state_root / 'installed.json'
    prior_state = None
    if state_file.exists():
        previous = json.loads(state_file.read_text(encoding='utf-8'))
        require(previous.get('status') in ['installed', 'uninstalled'],
                '上次安装未结束，请按记录恢复：' + str(state_file))
        if previous['status'] == 'installed':
            require(previous.get('mode') == 'macos-side-by-side' and
                    previous.get('targetBundle') == str(target) and previous.get('pet') == str(pet),
                    '上次安装使用了其他 App 或宠物路径；请先卸载该次安装。')
            verify_mac_bundle(target, previous['installedAppSha256'],
                              previous['installedAsarIntegrity'])
            require(tree_hashes(pet) == desired,
                    '安装后的宠物已改变；请保留现状并检查 installed.json。')
            print('已安装同一版奶蛙 v4.6.1，无需重复操作。')
            return previous
        prior_state = previous.get('previousInstallation')
    require(not target.exists(), '目标 App 已存在；为避免覆盖，请先移走它或更换 --target-app：' + str(target))
    require(not target.is_symlink(), '目标 App 不能是符号链接。')
    target.parent.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)
    backup = state_root / ('backup-' + time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    backup.mkdir()
    if had_pet:
        shutil.copytree(pet, backup / 'pet')
        require(tree_hashes(backup / 'pet') == original_pet, '宠物备份校验失败。')
    pet.parent.mkdir(parents=True, exist_ok=True)
    pet_stage = pet.with_name('naifrog-stage-' + uuid.uuid4().hex)
    displaced = pet.with_name('naifrog-previous-' + uuid.uuid4().hex)
    app_stage = target.with_name('.' + target.name + '.naifrog-' + uuid.uuid4().hex + '.stage')
    display_name = source_bundle.stem + ' 奶蛙'
    record = {
        'status': 'prepared', 'mode': 'macos-side-by-side', 'revision': 'v4.6.1',
        'build': spec['id'], 'sourceBundle': str(source_bundle), 'targetBundle': str(target),
        'app': str(target / 'Contents/Resources/app.asar'), 'pet': str(pet), 'backup': str(backup),
        'beforeAppSha256': info['sha256'], 'installedAppSha256': spec['patched'],
        'hadPet': had_pet, 'beforePetFiles': original_pet, 'installedPetFiles': desired,
        'restartRequired': True,
    }
    if prior_state:
        record['previousInstallation'] = prior_state
    app_installed = False
    pet_changed = False
    write_json(state_file, record)
    try:
        shutil.copytree(BUNDLE / 'pet', pet_stage)
        require(tree_hashes(pet_stage) == desired, '宠物暂存校验失败。')
        print('正在生成独立的 macOS 奶蛙 App（官方 App 保持不变）…', flush=True)
        clone_app(source_bundle, app_stage)
        staged_asar = app_stage / 'Contents/Resources/app.asar'
        with tempfile.NamedTemporaryFile(prefix='naifrog-', suffix='.asar',
                                         dir=str(staged_asar.parent), delete=False) as stream:
            patched = Path(stream.name)
        try:
            build_archive(staged_asar, patched, spec)
            os.chmod(patched, staged_asar.stat().st_mode & 0o777)
            os.replace(patched, staged_asar)
        finally:
            if patched.exists():
                patched.unlink()
        integrity = update_mac_integrity(app_stage, display_name)
        record['installedAsarIntegrity'] = integrity
        sign_mac_bundle(app_stage)
        verify_mac_bundle(app_stage, spec['patched'], integrity)
        require(not target.exists(), '目标 App 在安装期间出现；拒绝覆盖：' + str(target))
        os.replace(app_stage, target)
        app_installed = True
        if had_pet:
            os.replace(pet, displaced)
        os.replace(pet_stage, pet)
        pet_changed = True
        require(tree_hashes(pet) == desired, '宠物安装后校验失败。')
        verify_mac_bundle(target, spec['patched'], integrity)
        record['status'] = 'installed'
        write_json(state_file, record)
    except BaseException:
        if pet_changed and pet.exists():
            require(tree_hashes(pet) == desired,
                    '回滚前发现宠物被其他程序改变，请使用备份手动恢复：' + str(backup))
            shutil.rmtree(pet)
        if displaced.exists():
            os.replace(displaced, pet)
        if app_installed and target.exists():
            verify_mac_bundle(target, spec['patched'], record.get('installedAsarIntegrity'))
            shutil.rmtree(target)
        record['status'] = 'uninstalled'
        write_json(state_file, prior_state or record)
        raise
    finally:
        if pet_stage.exists():
            shutil.rmtree(pet_stage)
        if app_stage.exists():
            shutil.rmtree(app_stage)
    if displaced.exists():
        shutil.rmtree(displaced)
    print('安装完成：' + str(target))
    print('官方 App 未修改：' + str(source_bundle))
    print('请完全退出官方 App，再打开上面的“奶蛙”App，并在宠物列表选择“奶蛙”。')
    return record


def uninstall_linux(record, state_file, home):
    app, pet, backup = [Path(record[key]) for key in ['app', 'pet', 'backup']]
    require(pet == home / 'pets/naifrog', '安装记录与指定 Codex 目录不匹配。')
    require(sha(app) == record['installedAppSha256'] and
            tree_hashes(pet) == record['installedPetFiles'],
            'App 已升级或宠物已被修改，拒绝用旧备份覆盖；备份仍在：' + str(backup))
    require(sha(backup / 'app.asar') == record['beforeAppSha256'], 'App 备份已损坏。')
    if record['hadPet']:
        require(tree_hashes(backup / 'pet') == record['beforePetFiles'], '宠物备份已损坏。')
    stage = pet.with_name('naifrog-restore-' + uuid.uuid4().hex)
    current = pet.with_name('naifrog-remove-' + uuid.uuid4().hex)
    if record['hadPet']:
        shutil.copytree(backup / 'pet', stage)
    shutil.copy2(app, backup / 'uninstall-current.asar')
    app_changed = False
    try:
        if record['beforeAppSha256'] != record['installedAppSha256']:
            replace_app(backup / 'app.asar', app, record['installedAppSha256'])
            app_changed = True
        os.replace(pet, current)
        if record['hadPet']:
            os.replace(stage, pet)
        require(tree_hashes(pet) == record['beforePetFiles'], '卸载后的宠物校验失败。')
        record['status'] = 'uninstalled'
        write_json(state_file, record.get('previousInstallation') or record)
    except BaseException:
        if current.exists():
            if pet.exists():
                shutil.rmtree(pet)
            os.replace(current, pet)
        if app_changed:
            replace_app(backup / 'uninstall-current.asar', app, record['beforeAppSha256'])
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    shutil.rmtree(current)
    (backup / 'uninstall-current.asar').unlink()
    print('已恢复安装前的 App 和宠物。请完全退出并重新打开 Codex。备份保留。')


def uninstall_macos(record, state_file, home):
    target, pet, backup = [Path(record[key]) for key in ['targetBundle', 'pet', 'backup']]
    require(pet == home / 'pets/naifrog', '安装记录与指定 Codex 目录不匹配。')
    verify_mac_bundle(target, record['installedAppSha256'], record['installedAsarIntegrity'])
    require(tree_hashes(pet) == record['installedPetFiles'],
            '宠物已被修改，拒绝自动删除；备份仍在：' + str(backup))
    if record['hadPet']:
        require(tree_hashes(backup / 'pet') == record['beforePetFiles'], '宠物备份已损坏。')
    stage = pet.with_name('naifrog-restore-' + uuid.uuid4().hex)
    current = pet.with_name('naifrog-remove-' + uuid.uuid4().hex)
    removed_app = target.with_name('.' + target.name + '.naifrog-remove-' + uuid.uuid4().hex)
    if record['hadPet']:
        shutil.copytree(backup / 'pet', stage)
    os.replace(pet, current)
    target_moved = False
    try:
        if record['hadPet']:
            os.replace(stage, pet)
        require(tree_hashes(pet) == record['beforePetFiles'], '卸载后的宠物校验失败。')
        verify_mac_bundle(target, record['installedAppSha256'], record['installedAsarIntegrity'])
        os.replace(target, removed_app)
        target_moved = True
        record['status'] = 'uninstalled'
        write_json(state_file, record.get('previousInstallation') or record)
    except BaseException:
        if target_moved and removed_app.exists():
            os.replace(removed_app, target)
        if current.exists():
            if pet.exists():
                shutil.rmtree(pet)
            os.replace(current, pet)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    shutil.rmtree(current)
    shutil.rmtree(removed_app)
    print('已移除独立的奶蛙 App，并恢复安装前的宠物。官方 App 始终未被修改。备份保留。')


def uninstall(home):
    state_file = home / 'naifrog-installer/installed.json'
    require(state_file.is_file(), '没有找到本安装包的安装记录。')
    record = json.loads(state_file.read_text(encoding='utf-8'))
    if record.get('status') == 'uninstalled':
        print('已经卸载。备份保留。')
        return
    require(record.get('status') == 'installed',
            '上次事务尚未完成，请根据记录检查备份：' + str(state_file))
    if record.get('mode') == 'macos-side-by-side':
        uninstall_macos(record, state_file, home)
    else:
        uninstall_linux(record, state_file, home)


def main():
    parser = argparse.ArgumentParser(description='奶蛙 v4.6.1 Linux / macOS 离线安装包')
    parser.add_argument('command', choices=['check', 'install', 'uninstall'], nargs='?', default='check')
    parser.add_argument('--app', help='Codex/ChatGPT .app 或 resources/app.asar 的实际路径')
    parser.add_argument('--target-app', help='macOS 独立奶蛙 App 的目标路径（默认 ~/Applications）')
    parser.add_argument('--codex-home', default=os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    args = parser.parse_args()
    key = platform_key()
    require(key in ['linux', 'darwin'], '此安装包仅支持 Linux 和 macOS。')
    require(os.geteuid() != 0, '请用自己的普通用户运行，不要 sudo 整个脚本。')
    home = Path(args.codex_home).expanduser().resolve()
    if args.command == 'uninstall':
        uninstall(home)
        return
    verify_bundle()
    app = discover(args.app, key)
    if args.command == 'check':
        report = inspect(app, key)
        if key == 'darwin':
            report['suggestedTargetBundle'] = str(mac_target_path(mac_bundle_for_asar(app), args.target_app))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        require(report['supported'], '这个版本尚未适配。检查没有修改任何 App 或宠物文件。')
    elif key == 'darwin':
        install_macos(app, home, args.target_app)
    else:
        require(args.target_app is None, '--target-app 仅用于 macOS。')
        install_linux(app, home)


if __name__ == '__main__':
    try:
        main()
    except (InstallError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print('未完成：' + str(error), file=sys.stderr)
        sys.exit(1)
