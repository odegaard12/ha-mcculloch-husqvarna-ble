# Cambios

Todas las versiones de la integración, la tarjeta y la app. Lo más nuevo, arriba.

## v0.3.7 · El robot pisa el césped en la tarjeta

_En la tarjeta el robot ya no flota sobre el horizonte: se coloca en el centro del césped._

#### Tarjeta
- **El robot pisa el césped**: el render trae un margen transparente debajo y el robot quedaba pegado al horizonte, como flotando. Ahora se coloca en el centro del césped (también volcado o levantado).


## v0.3.6 · La tarjeta vuelve a cargar siempre y robots en gris sin conexión

_Arreglo del «error de configuración» de la tarjeta en algunos paneles, robot en gris sobre césped verde cuando no hay conexión e icono de la app más grande._

#### Tarjeta
- **Ya no sale «error de configuración»** (Custom element doesn't exist): algunas tarjetas de HACS cambian el registro de elementos del navegador por otro después de cargar esta, y el nuevo no la conocía. Ahora se vuelve a registrar sola si desaparece.
- **Sin conexión, el césped se queda verde** y solo el robot pasa a gris (opaco, sin transparencia).

#### App (panel web)
- Mismo cambio de aspecto sin conexión: césped verde y robot gris.
- **Icono de la cabecera recortado al robot**: antes salía diminuto dentro del cuadro.
- **Botones apagados sin conexión**: Cortar, Pausa y A la base se ven en gris y, al pulsarlos, explican por qué en vez de esperar a que falle la orden.


## v0.3.5 · Revisión a fondo: jardín nuevo, averías legibles y fallos

_Revisión completa de la app, la tarjeta y la integración: diseño del jardín, averías legibles y una docena de fallos menos._

#### Diseño
- **Jardín nuevo** en la app y en la tarjeta: cielo con degradado (de noche, con estrellas), setos al fondo, césped con franjas de corte, foco de luz bajo el robot y briznas en dos capas.
- **Las averías no tapan la batería**: arriba solo «Avería»; qué avería es y qué hacer, debajo.
- Fundido al cambiar de pestaña y salto suave de la etiqueta cuando cambia el estado.
- Sin conexión y sin horario conocido dice «se sabrá al conectar», no «sin horario».

#### App (panel web)
- **Nombres y contraseñas entre dos servidores**: gana el cambio más nuevo, se reintenta si el otro no responde y se sincronizan al arrancar. Una copia vieja reenviada no pisa nada.
- **Avisos**: un móvil sin red ya no hace repetir avisos; al desbloquear o bloquear un robot, los avisos del móvil se ponen al día solos; solo se aceptan servicios push reales; dos avisos a la vez no se pisan el registro.
- Al desbloquear o cambiar de robot no se ve nada del anterior mientras llegan sus datos.
- Sin dato ya no salen «0 choques» ni «0 ciclos», ni el estado «unknown» en inglés.
- Una sola lectura de datos a la vez: una respuesta lenta y vieja no pisa una nueva.
- La página lleva su versión: una copia guardada sin red se actualiza en cuanto vuelve la red.

#### Integración
- Con un PIN incorrecto la conexión Bluetooth ya no se queda abierta (impedía volver a configurarlo).
- Al descargar la integración se cierra también el «mantener vivo».
- Un sondeo cortado a medias no borra entidades.
- Una lectura fallida del horario no se guarda como «sin horario».
- Los servicios dan mensajes claros en español con el robot fuera de alcance.
- Traducción al inglés completa.

#### Tarjeta
- Las imágenes llevan la versión: nunca se mezclan vistas viejas y nuevas.
- La animación se para con el robot quieto (menos batería en el móvil).
- El horario guardado no se borra por una lectura fallida.

## v0.3.4 · Giro 3D con el dedo, un color por robot y textos sin cortes

_El robot se gira con el dedo, cada robot tiene su color y ya no se ven textos cortados._

#### Novedades
- **El robot se gira con el dedo**, en la app y en la tarjeta: vuelta entera con inercia; a los 3 s vuelve solo a lo que estaba haciendo.
- **Un color y un icono por robot**: amarillo el McCulloch, naranja el Landroid.
- **Teclado numérico** para la contraseña del robot bloqueado.
- **Tirar hacia abajo para actualizar**, y fundido al cambiar de robot.

#### Correcciones
- Nunca se mezcla un robot con otro: mientras cargan sus vistas no se enseña nada, y la app arranca con el último robot visto.
- Textos que no se cortan: barra de robots y averías en dos líneas; la tabla de datos parte los valores largos.
- La pantalla de contraseña tenía el título partido y había un óvalo translúcido sobre el robot.
- La app no se recarga sola mientras escribes una contraseña.

#### Repositorio
- Título, textos, capturas completas y nombres (HACS, complemento y selector de tarjetas) con los dos robots.

## v0.3.3 · Landroid en 3D, tarjeta para dos robots y contraseña por robot

_El Landroid tiene su propio modelo 3D, la tarjeta enseña dos robots, cada robot puede llevar contraseña y todas las averías salen en español._

#### Novedades
- **Modelo 3D del Worx Landroid** hecho en Blender: capó naranja en U con faldón de aletas, chasis negro, batería PowerShare, ruedas de tacos, mando de altura y pantalla con STOP. 24 vistas y base de carga.
- **Tarjeta para dos robots** (`entity_2` y `name_2`, también desde el editor), cada uno con su modelo y sus órdenes.
- **Nombre de cada robot** desde la barra de arriba de la app, igual en todos los móviles.
- **Contraseña por robot**: sin ella, en los demás móviles no se ven sus datos ni se le dan órdenes. Lo comprueba el servidor.
- **Avisos push del Landroid**, con el nombre de cada robot.

#### Correcciones
- **Averías en español**: los 160 códigos traducidos en HA, la app, la tarjeta y los avisos. El sensor de error añade el atributo `descripcion`.
- Al volver a la base el robot se queda a medio entrar; ya no parece aparcado sin cargar.
- El aviso de «sin conexión» ya no se repite cada 6 horas por la misma desconexión.

## v0.3.2 · Dos robots en la app: McCulloch y Worx Landroid

_La app maneja varios robots a la vez; el primero que se suma es un Worx Landroid._

#### Novedades
- **Varios robots en la misma app**: barra arriba con el estado y la batería de cada uno para cambiar de robot, y ficha **Mis robots**. Recuerda el último que viste.
- **Worx Landroid** (integración Landroid Cloud): estado, batería, horario (solo consulta), actividad de 24 h y 7 días, error, lluvia, señal Wi-Fi, uso acumulado, sus interruptores y las órdenes Cortar, Pausa, A la base y Cortar solo los bordes.
- Opción `ROBOTS` (`prefijo:nombre:tipo`), también en el complemento como `robots`.

#### Correcciones
- Sin dato de batería se veía «0 %»; ahora sale «–».
- Los interruptores se desactivan mientras el robot no está conectado.

## v0.3.1 · Vuelta al diseño anterior del robot

_El modelo 3D recupera el diseño de la v0.2.8, más limpio._

#### Diseño
- El modelo 3D vuelve al de la v0.2.8, sin el bloque de teclado sobre la tapa.

#### Repositorio
- `CHANGELOG.md` con toda la historia y notas de versión reescritas.

## v0.3.0 · Avisos push, últimos datos sin cobertura y autoactualización

_La app instalada avisa de averías y desconexiones, y sin cobertura sigue enseñando los últimos datos._

#### Novedades
- **Avisos push en la app instalada**: avería, vuelco, robot levantado, parado en el jardín y 1 o 3 días sin conexión.
  - Sin consultas periódicas: escucha los cambios de Home Assistant.
  - Cada aviso, como mucho una vez cada 6 h y nunca más de 6 al día.
- **Últimos datos sin cobertura**: con el robot lejos se siguen viendo horario, batería y estadísticas. Se guardan en disco y sobreviven a los reinicios.
- Sensor **Última conexión**, siempre disponible.
- La app se recarga sola cuando hay una versión nueva.
- Plantilla de avisos para la app de Home Assistant (`blueprints/`).

## v0.2.8 · Modelo más realista y base de carga con piloto

_Más detalle en el robot y una base con piloto que parpadea al cargar._

#### Novedades
- Modelo más realista: radios curvos, neumático en espiga y línea de faldón.
- Base de carga con piloto que parpadea mientras carga, en la app y en la tarjeta.
- En la tarjeta, el robot entra rodando en la base y sale marcha atrás.

#### Correcciones
- Sin conexión, el próximo corte se calcula con el horario guardado.

## v0.2.7 · Tarjeta bien encuadrada en pantallas anchas

_El robot ya no se sale de la tarjeta en pantallas anchas._

#### Correcciones
- El robot se dimensiona por la altura de la escena: no se sale del recuadro y apoya en el césped.
- El robot volcado se ve por encima de la hierba.

## v0.2.6 · Modelo 3D propio hecho en Blender

_El robot y su base pasan a ser un modelo 3D propio, sin logotipos, renderizado desde 24 ángulos._

#### Novedades
- Robot y base de carga generados por script en Blender (`tools/blender`), sin logotipos.
- Al cortar, el robot gira de verdad al final de cada pasada.
- Al volver entra rodando en la base y al salir se separa marcha atrás.
- Quieto, se puede girar arrastrando el dedo.
- Indicaciones en cada estado: hasta qué hora corta, cuánto le falta para cargar, qué hacer si se vuelca.

## v0.2.5 · Robot que gira en 3D y horas cortadas por día

_El robot gira en 3D al cortar y al volcarse, y hay una gráfica de la semana._

#### Novedades
- El robot gira en 3D al final de cada pasada y da la vuelta si se vuelca.
- Gráfica de horas cortadas por día de la última semana.

#### Seguridad
- Cabeceras de seguridad en la app: política de contenido y nada de marcos ajenos.

#### App (panel web)
- Punto de salud `/api/salud` para comprobar los despliegues.

#### Repositorio
- README con capturas.

## v0.2.4 · Revisión de seguridad y fiabilidad

_Más seguridad en la app y una integración que aguanta mejor los cortes de Bluetooth._

#### Seguridad
- Lista blanca de órdenes estricta: una sola entidad del robot, nunca listas separadas por comas.
- Límite global de intentos de PIN, además del límite por dirección.
- Las sesiones dependen del PIN: si lo cambias, las anteriores dejan de valer.
- El diagnóstico descargable va sin MAC, números de serie ni nombre del robot.

#### Integración
- Si el robot está lejos al arrancar, ya no desaparece de HA: sale como no disponible y reintenta solo.
- Todas las órdenes Bluetooth esperan a que termine de grabarse el horario.
- Paso para cambiar el PIN del robot desde la interfaz.
- «Parado en el jardín» se muestra como pausa, no como avería.

#### Tarjeta
- Los textos de los sensores se pintan siempre como texto.
- Las fechas salen en la zona horaria de Home Assistant.

## v0.2.3 · Foto propia en la tarjeta y app sin zoom

_Puedes poner tu propia foto del robot en la tarjeta, y la app deja de ampliarse por error._

#### Tarjeta
- Opción `image` para usar tu propia foto; no se pierde al actualizar.

#### App (panel web)
- Sin zoom por doble toque, por pellizco ni al escribir, como una app nativa.

## v0.2.2 · La tarjeta carga siempre y los datos llegan desde el arranque

_La tarjeta ya no falla en la app del móvil y los datos lentos aparecen desde la primera lectura._

#### Correcciones
- La tarjeta se registra también como recurso de Lovelace: la app de Home Assistant la carga aunque tenga la página guardada.
- Estadísticas, ajustes y horario se leen en la primera lectura tras arrancar; antes tardaban 10 minutos si el equipo acababa de encenderse.
- La tarjeta reconoce las entidades creadas con versiones anteriores.

## v0.2.1 · Primera versión pública

_Integración Bluetooth sin nube para robots McCulloch ROB, Husqvarna Automower, Gardena SILENO y Flymo Easilife, con tarjeta animada y panel web._

#### Integración
- Unas 50 entidades: batería, estado, actividad, próximo corte, avería, choques, levantado, volcado, estadísticas y ajustes.
- Órdenes: cortar, pausa y volver a la base.
- Servicios: editar el horario semanal (`set_schedule`), cortar o aparcar X horas (`mow_for`, `park_for`), enviar cualquier comando del protocolo (`send_command`) y comprobar qué responde cada modelo (`probe`).
- Librería AutoMower-BLE incluida con dos arreglos: espera de 1 s antes de abrir el canal y respuestas de un solo campo.

#### Tarjeta
- Va dentro de la integración: robot animado según su estado, batería, próximo corte y órdenes rápidas.

#### App (panel web)
- Instalable en el móvil como una app: como complemento de Home Assistant, en Docker o en una Raspberry.
