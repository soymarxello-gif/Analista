# Validación de Analista 1.81.0

## Cambio de comportamiento

- Selección y ranking basados exclusivamente en elegibilidad confirmada y setup técnico.
- Macro, fundamentales, earnings, opciones y sentimiento quedan fuera del score de selección.
- Contexto ausente se informa con mensajes explícitos como `Sin datos de opciones`.
- Ningún dato contextual ausente o adverso cambia el score, la señal o la elegibilidad.
- Market cap ausente permite continuar con advertencia; un valor conocido bajo el mínimo conserva el veto.

## Controles ejecutados

| Control | Resultado |
|---|---:|
| Pytest | 79 aprobadas |
| Ruff | Aprobado |
| Validadores CI Python | 17 aprobados |
| Validador lógico adicional | Aprobado |
| `compileall` y `git diff --check` | Aprobados |
| Kotlin/Android en esta sesión | Pendiente de SDK/Gradle completo |

Las pruebas incluyen invariancia explícita: cambiar macro, fundamentales, opciones y sentimiento desde valores mínimos a máximos no modifica el score técnico; eliminar esos datos tampoco elimina señales. Los componentes técnicos opcionales ausentes se omiten y los pesos disponibles se renormalizan, sin imputar 50 ni penalizar.
