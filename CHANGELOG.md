# Cambios

Todas las versiones de la integración, la tarjeta y el panel web.

## v0.3.2 · Varios robots en el panel: McCulloch y Worx Landroid

#### Novedades
- **Varios robots en la misma app**: barra arriba con cada robot (estado y batería) para cambiar de uno a otro, y ficha **Mis robots** al tocar el título. Recuerda el último que viste.
- **Worx Landroid** (integración Landroid Cloud):
  - estado, batería y horario guardado (solo para consultar);
  - actividad de 24 h y de 7 días, error, lluvia, señal Wi-Fi y uso acumulado;
  - sus interruptores y las órdenes Cortar, Pausa, A la base y Cortar solo los bordes.
- Opción nueva `ROBOTS` (`prefijo:nombre:tipo`), también en el complemento como `robots`.

#### Correcciones
- Sin dato de batería, el panel mostraba «0 %»; ahora muestra «–».
- Los interruptores quedan desactivados mientras el robot no está conectado.

## v0.3.1 · Vuelta al diseño anterior del robot

#### Cambios
- El modelo 3D vuelve al diseño de la v0.2.8, sin el bloque de teclado sobre la tapa, que restaba más que sumaba.
- `CHANGELOG.md` con la historia del proyecto y notas de versión reescritas.

## v0.3.0 · Avisos push, últimos datos sin cobertura y actualización automática

#### Novedades
- **Avisos push en la web app instalada**: avería, vuelco, robot levantado, parado en el jardín y 1 o 3 días sin conexión.
  - Sin consultas periódicas: se suscribe a los cambios de Home Assistant.
  - Cada aviso sale como mucho una vez cada 6 h y nunca más de 6 al día.
- **Últimos datos sin cobertura**: con el robot lejos se siguen viendo el horario, la batería y las estadísticas. Se guardan en disco y sobreviven a los reinicios.
- Sensor nuevo **Última conexión**, siempre disponible.
- La app se recarga sola cuando hay una versión nueva.
- Plantilla de avisos para la app de Home Assistant (`blueprints/`).

## v0.2.8 · Modelo más realista y base de carga con piloto

#### Novedades
- Modelo más realista: radios curvos en aspa, neumático en espiga y línea de faldón.
- Base de carga con piloto que parpadea mientras carga, en el panel y en la tarjeta.
- En la tarjeta, el robot entra rodando en la base y sale marcha atrás.
- Si el robot no conecta, el próximo corte se calcula a partir del horario guardado.

## v0.2.7 · Tarjeta correcta en pantallas anchas

#### Correcciones
- El robot se dimensiona por la altura de la escena: ya no se sale del recuadro en tarjetas anchas y apoya en el césped.
- El robot volcado se ve por encima de la hierba.

## v0.2.6 · Modelo 3D propio hecho en Blender

#### Novedades
- El robot y la base de carga son un modelo 3D propio, generado por script en Blender (`tools/blender`) y sin logotipos, renderizado desde 24 ángulos.
- Al cortar, el robot gira de verdad al final de cada pasada.
- Al volver entra rodando en la base y al salir se separa marcha atrás.
- Quieto, se puede girar arrastrando el dedo.
- Indicaciones en todos los estados: hasta qué hora corta, cuánto falta para que se cargue, qué hacer si se vuelca…

## v0.2.5 · Animación 3D, gráfica semanal y cabeceras de seguridad

#### Novedades
- El robot gira en 3D al final de cada pasada al cortar y da la vuelta en 3D si se vuelca.
- Gráfica de horas cortadas por día en la última semana.

#### Panel web
- Cabeceras de seguridad: CSP y nada de iframes ajenos.
- Punto de salud `/api/salud` para comprobar despliegues.
- README con capturas.

## v0.2.4 · Revisión de seguridad y fiabilidad

#### Seguridad (panel web)
- Lista blanca de órdenes estricta: solo una entidad del robot, nunca listas separadas por comas.
- Límite global de intentos de PIN, además del límite por IP.
- Las sesiones quedan ligadas al PIN: si lo cambias, las anteriores dejan de valer.

#### Integración
- El robot ya no desaparece de HA si está lejos al arrancar: sale como no disponible y reintenta solo.
- Todas las órdenes Bluetooth respetan el bloqueo durante la grabación del horario.
- Paso para cambiar el PIN del robot desde la interfaz.
- El diagnóstico descargable va sin MAC, sin números de serie y sin el nombre del robot.
- "Parado en el jardín" se muestra como pausa, no como avería.

#### Tarjeta
- Los textos de los sensores se muestran siempre como texto.
- Las fechas salen en la zona horaria de HA.

## v0.2.3 · Foto propia en la tarjeta y panel sin zoom

#### Novedades
- Opción `image` en la tarjeta para usar tu propia foto sin que se pierda al actualizar.

#### Panel web
- Sin zoom por doble toque, por pellizco ni al escribir, como una app.

## v0.2.2 · La tarjeta se registra sola y lectura completa al arrancar

#### Correcciones
- La tarjeta se registra también como recurso de Lovelace, así que la app del móvil la carga aunque tenga la página en caché.
- Estadísticas, ajustes y horario se leen también en la primera lectura después de arrancar el equipo. Antes tardaban 10 minutos en aparecer si el equipo llevaba poco tiempo encendido.
- La tarjeta reconoce las entidades creadas con versiones anteriores.

## v0.2.1 · Primera versión pública

Integración Bluetooth para robots McCulloch ROB, Husqvarna Automower, Gardena SILENO y Flymo Easilife, sin nube.

#### Integración
- Unas 50 entidades: batería, estado, actividad, próximo corte, errores, sensores de choque, levantado y volcado, estadísticas y ajustes.
- Órdenes: cortar, pausa, volver a la base.
- Servicios: editar el horario semanal (`set_schedule`), cortar o aparcar durante X horas (`mow_for`, `park_for`), enviar cualquier comando del protocolo (`send_command`) y sondear lo que responde cada modelo (`probe`).
- Librería AutoMower-BLE incluida con dos arreglos: espera de 1 s antes de abrir el canal y respuestas de un solo campo.

#### Tarjeta de Lovelace
- Incluida en la integración, sin instalar nada aparte: robot animado según su estado, batería, próximo corte y órdenes rápidas.

#### Panel web
- Estilo app e instalable en el móvil, como complemento de Home Assistant, en Docker o en una Raspberry.
