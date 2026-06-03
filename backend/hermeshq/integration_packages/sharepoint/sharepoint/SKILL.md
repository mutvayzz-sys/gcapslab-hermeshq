---
name: sharepoint
description: Navegar, buscar y acceder a archivos en SharePoint y OneDrive del usuario.
---

# SharePoint & OneDrive Skill

Usa esta skill cuando el usuario necesite explorar, buscar o acceder a documentos en SharePoint o OneDrive.

## Herramientas disponibles

- `sharepoint_list_drives` — Lista las unidades disponibles (OneDrive + bibliotecas SharePoint)
- `sharepoint_list_files` — Lista archivos en OneDrive o en un sitio SharePoint específico
- `sharepoint_get_file` — Obtiene información de un archivo por su ruta
- `sharepoint_search` — Busca documentos usando Microsoft Search

## Uso correcto

- Usa `sharepoint_list_drives` para descubrir qué unidades tiene el usuario
- Para acceder a un sitio SharePoint específico, provee la `site_url` (ej: `https://empresa.sharepoint.com/sites/Marketing`)
- Sin `site_url`, opera sobre el OneDrive personal del usuario
- Usa `sharepoint_search` para encontrar documentos por nombre o contenido

## Notas

- Usa permisos `Files.Read.All` del usuario autenticado
- El usuario debe tener su cuenta M365 conectada en Mi cuenta
