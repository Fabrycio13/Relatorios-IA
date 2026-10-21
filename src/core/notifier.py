import base64
import subprocess
import sys
from src.core.logger import get_logger

logger = get_logger("notifier")

def notificar_windows(titulo: str, mensagem: str):
    """Dispara uma notificação nativa do Windows (Toast) em caso de erro crítico ou conclusão."""
    if sys.platform != "win32":
        return
    try:
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName('text')
        $textNodes.Item(0).AppendChild($template.CreateTextNode('{titulo}')) | Out-Null
        $textNodes.Item(1).AppendChild($template.CreateTextNode('{mensagem}')) | Out-Null
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
