# WordPad em português de Portugal

Versão independente do WordPad para Windows com interface em **português de Portugal (`pt-PT`)**. O executável e a biblioteca auxiliar não foram modificados; foi criado um novo recurso linguístico `pt-PT/wordpad.exe.mui` a partir da versão inglesa fornecida.

> Esta não é uma tradução oficial da Microsoft. Consulte [NOTICE.md](NOTICE.md) antes de redistribuir os ficheiros.

## Instalação

1. Transfira `WordPad-PT-PT.zip` da página [**Releases**](https://github.com/araujom/wordpad-pt-pt/releases/latest).
2. Antes de extrair, clique no ZIP com o botão direito e escolha **Propriedades**. No separador **Geral**, se aparecer a opção **Desbloquear**, assinale-a e selecione **Aplicar** e **OK**. Esta opção pode não aparecer, o que é normal.
3. Extraia o ZIP e copie a pasta completa `WordPad-PT-PT` para uma destas localizações:

   - `C:\Users\<o-seu-nome>\WordPad-PT-PT` — não costuma exigir permissões de administrador;
   - `C:\Program Files\WordPad-PT-PT` — localização recomendada para todos os utilizadores; requer permissões de administrador.

4. Não copie apenas o executável. Mantenha esta estrutura dentro da pasta:

   ```text
   WordPad-PT-PT/
   ├── wordpad.exe
   ├── WordpadFilter.dll
   ├── en-US/
   │   └── wordpad.exe.mui
   └── pt-PT/
       └── wordpad.exe.mui
   ```

5. Abra `wordpad.exe` num Windows configurado para **Português (Portugal)**.

Pode guardar a pasta noutro local, se preferir. Não substitua uma instalação existente do WordPad em `C:\Program Files\Windows NT\Accessories` e não mova os ficheiros `.mui` para fora das respetivas pastas de idioma.

### Segurança e avisos do Windows

A opção **Desbloquear** não certifica que uma aplicação é de confiança: apenas remove a marca que o Windows coloca nos ficheiros transferidos da Internet. Utilize-a somente depois de confirmar que o ZIP veio deste repositório. A [Microsoft explica este comportamento](https://support.microsoft.com/windows/security/information-about-the-attachment-manager-in-microsoft-windows) na documentação do Gestor de Anexos.

Antes da primeira utilização:

1. Abra a pasta extraída, clique em `wordpad.exe` com o botão direito e escolha **Analisar com o Microsoft Defender** (ou com o antivírus instalado).
2. Para confirmar a integridade dos ficheiros, compare os respetivos valores SHA-256 com [`SHA256SUMS.txt`](SHA256SUMS.txt). Um hash coincidente confirma que o ficheiro não foi alterado; por si só, não prova que seja seguro.
3. Se o Microsoft Defender SmartScreen apresentar **O Windows protegeu o PC**, confirme novamente a origem e o resultado da análise. Apenas se confiar no ficheiro, selecione **Mais informações** e **Executar mesmo assim**. Não é necessário desativar o Defender nem o SmartScreen.

O `wordpad.exe` incluído não foi modificado por este projeto, mas a cópia de origem não contém uma assinatura digital incorporada. O recurso `pt-PT/wordpad.exe.mui` é uma tradução comunitária criada neste repositório e também não é assinado pela Microsoft. Por esse motivo, um aviso do SmartScreen pode ser esperado.

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
