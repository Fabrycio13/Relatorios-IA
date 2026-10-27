import base64
import subprocess
import sys
from src.core.logger import get_logger

logger = get_logger("notifier")


def _sanitizar_texto_toast(texto: str | None) -> str:
    """
    Remove caracteres de controle inválidos para XML 1.0 (ex: NULL, BEL, etc.),
    preservando quebras de linha (\n, \r), tabulações (\t) e caracteres imprimíveis.
    """
    if not texto:
        return ""
    return "".join(
        ch for ch in str(texto)
        if ch in ("\t", "\n", "\r") or (ord(ch) >= 0x20 and ord(ch) != 0x7F)
    )


def notificar_windows(titulo: str, mensagem: str):
    """
    Dispara uma notificação nativa do Windows (Toast) em caso de erro crítico, conclusão ou preview.
    Transporta os parâmetros via Base64 UTF-8 para garantir imunidade contra quebras de sintaxe
    provocadas por aspas simples, apóstrofos, aspas duplas, quebras de linha ou caracteres especiais.
    """
    if sys.platform != "win32":
        return
    try:
        titulo_limpo = _sanitizar_texto_toast(titulo)
        mensagem_limpa = _sanitizar_texto_toast(mensagem)

        # Serialização segura para transporte sem interpolação direta de texto no script
        titulo_b64 = base64.b64encode(titulo_limpo.encode("utf-8")).decode("ascii")
        mensagem_b64 = base64.b64encode(mensagem_limpa.encode("utf-8")).decode("ascii")

        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName('text')
        $title = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{titulo_b64}'))
        $msg = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{mensagem_b64}'))
        $textNodes.Item(0).AppendChild($template.CreateTextNode($title)) | Out-Null
        $textNodes.Item(1).AppendChild($template.CreateTextNode($msg)) | Out-Null
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Diário de IA')
        $notification = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier.Show($notification)
        """
        enc = base64.b64encode(ps_script.encode("utf-16le")).decode("utf-8")
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
            timeout=5,
            capture_output=True,
            check=False
        )
    except Exception as e:
        logger.debug(f"Não foi possível exibir notificação nativa do Windows: {e}")

if __name__ == "__main__":
    notificar_windows("Diário de IA: Teste", "Notificação nativa do Windows configurada com sucesso!")
    print("Notificação executada!")
