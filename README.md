# WordPad em português de Portugal

Versão independente do WordPad para Windows com interface em **português de Portugal (`pt-PT`)**. O executável e a biblioteca auxiliar não foram modificados; foi criado um novo recurso linguístico `pt-PT/wordpad.exe.mui` a partir da versão inglesa fornecida.

> Esta não é uma tradução oficial da Microsoft. Consulte [NOTICE.md](NOTICE.md) antes de redistribuir os ficheiros.

## Utilização

1. Transfira o ZIP da página **Releases** e extraia-o.
2. Mantenha esta estrutura de pastas:

   ```text
   WordPad-PT-PT/
   ├── wordpad.exe
   ├── WordpadFilter.dll
   ├── en-US/
   │   └── wordpad.exe.mui
   └── pt-PT/
       └── wordpad.exe.mui
   ```

3. Abra `wordpad.exe` num Windows configurado para português (Portugal).

Pode utilizar a pasta em qualquer localização. Em alternativa, copie todo o conteúdo para:

```text
C:\Program Files\Windows NT\Accessories
```

Essa segunda opção normalmente requer permissões de administrador. Não mova os ficheiros `.mui` para fora das respetivas pastas de idioma.

## Conteúdo da tradução

A localização cobre:

- 457 textos da interface e descrições de comandos;
- 10 caixas de diálogo e 67 controlos com texto;
- o menu de ajuda;
- 51 mensagens internas;
- os metadados de versão e o identificador de idioma `0x0816` (`pt-PT`).

O mapeamento completo, identificador a identificador, encontra-se em [`translations/pt-PT.json`](translations/pt-PT.json).

## Validação

O processo de construção confirma automaticamente:

- a preservação integral da árvore de recursos original;
- a presença de todos os textos traduzidos;
- a manutenção dos marcadores de substituição, como `%1`, `%2`, `%d` e `%s`;
- o idioma `pt-PT` em todos os recursos e metadados MUI;
- a integridade estrutural do ficheiro PE e o respetivo checksum.

Os valores SHA-256 estão em [`SHA256SUMS.txt`](SHA256SUMS.txt). A validação efetuada neste projeto é estática; o ficheiro deve ser confirmado no computador Windows de destino.

## Recriar o recurso PT-PT

É necessário Python 3.9 ou posterior:

```text
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python tools\build_pt_pt.py
```

Em macOS ou Linux, utilize `.venv/bin/` em vez de `.venv\Scripts\`.

## Origem

Os ficheiros de referência foram obtidos da [pasta pública do Google Drive indicada para este projeto](https://drive.google.com/drive/folders/1eyeiHBlPZ0PkN5v1ohXKC5CAL4Qs_YAb). A tradução PT-PT foi preparada especificamente para este repositório.
