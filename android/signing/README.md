# Firma de producción

El repositorio no contiene ni descarga claves de firma compartidas. CI publica solamente un APK `debug` identificado explícitamente como no apto para producción.

Para publicar una variante `release`, configure un keystore privado fuera del repositorio o use Play App Signing. La contraseña, el alias y el keystore deben entrar mediante secretos protegidos del entorno de release. Nunca use la clave AOSP de prueba ni una clave descargable públicamente.
