from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField

from wagtail.models import Page
from home import blocks as block


class SenseBoxLocation(models.Model):
    class Meta:
        verbose_name_plural = "SenseBox Locations"
        verbose_name = "SenseBox Location"

    name = models.CharField(max_length=255, blank=True, help_text='(optional) Name des Ortes', default='leer')
    location_latitude = models.CharField(max_length=255, blank=False, default='52.516221',
                                         help_text='Latitude: Zentraler Punkt eines Ortes/ einer Stadt für den im Umkreis automatisch SenseBoxen ermittelt werden sollen.')
    location_longitude = models.CharField(max_length=255, default='13.3992',
                                          help_text='Longitude: Zentraler Punkt eines Ortes/ einer Stadt für den im Umkreis automatisch SenseBoxen ermittelt werden sollen.')
    maxDistance = models.IntegerField(help_text='Radius um den Mittelpunkt, der einbezogen werden soll in Metern.', null=False, default='30000')
    exposure = models.CharField(max_length=50, default='outdoor',
                                help_text='Welche Art von Sensor soll dargestellt werden? Erlaubte Werte: "indoor", "outdoor", "mobile", "unknown"')


class GroupTag(models.Model):
    tag = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['tag'],
                name='unique_tag_constraint',
                deferrable=models.Deferrable.DEFERRED
            )
        ]

    def __str__(self):
        return f'{self.tag}'


class SenseBoxTable(models.Model):
    class Meta:
        verbose_name_plural = "SenseBox Table"
        verbose_name = "SenseBox"

    sensebox_id = models.CharField(max_length=255, help_text='ID der SenseBox')
    name = models.CharField(max_length=255, blank=True, help_text='(optional) Name der SenseBox. Wird automatisch ermittelt')
    grouptags = models.ManyToManyField(GroupTag, blank=True, verbose_name='associated Group Tags')
    location_latitude = models.CharField(max_length=255, blank=True, null=True,
                                         help_text='(optional) Latitude der SenseBox. Wird automatisch ermittelt')
    location_longitude = models.CharField(max_length=255, blank=True, null=True,
                                          help_text='(optional) Longitude der SenseBox. Wird automatisch ermittelt')
    error_message = models.CharField(max_length=255, blank=True, null=True,
                                     help_text='Fehlermeldung der Box. Möglicherweise offline, fehlerhafte Werte etc. Box dann entfernen.')
    textfield = models.TextField(help_text='(optional) Textfeld für Notizen', blank=True)

    def __str__(self):
        return f'{self.sensebox_id} - {self.name}: [{self.location_latitude}, {self.location_longitude}]'


class SensorsInfoTable(models.Model):
    class Meta:
        verbose_name_plural = "Sensors Info Table"
        verbose_name = "Sensors Info"

    sensor_id = models.CharField(max_length=255, help_text='Sensor ID')
    sensor_name = models.CharField(max_length=255, help_text='Sensor Name')
    sensor_unit = models.CharField(max_length=255, help_text='Sensor Unit')
    sensor_type = models.CharField(max_length=255, help_text='Sensor Type')
    box_name = models.CharField(max_length=255, blank=True, help_text='Name des Sensors')
    box_grouptag = models.CharField(max_length=255, blank=True, help_text='Box Grouptag')
    lat = models.CharField(max_length=255, blank=True, help_text='Latitude')
    lon = models.CharField(max_length=255, blank=True, help_text='Longitude')

    def __str__(self):
        return f'{self.sensor_name} - {self.box_name}'


class HomePage(Page):
    parent_page_types = ['wagtailcore.Page']

    # header = StreamField([
    #    ('heros', block.HeroBlock()),
    # ], null=True, min_num=1, max_num=1)

    body = StreamField([
        ('statistics_placeholder', block.StatisticsPlaceholderBlock()),
        ('paragraph', block.ParagraphBlock()),
        #gif_image,
    ], default=None, null=True, blank=True)

    content_panels = Page.content_panels + [
        # FieldPanel('header'),
        # FieldPanel('blog'),
        FieldPanel('body'),
    ]

    def get_context(self, request, *args, **kwargs):
        # Update context to include only published posts, ordered by reverse-chron
        context = super().get_context(request, *args, **kwargs)

        sensebox_table = SenseBoxTable.objects.all()

        context['maptiler_key'] = 'nTN3lU7nRhNqaH2uJp8C'

        map_scripts = """"""

        """
        <script>
            var popup = L.popup();
            
            function onMapClick(e) {{
                popup
                    .setLatLng(e.latlng)
                    .setContent(e.latlng.toString())
                    .openOn(map);
            }}
            map.on('click', onMapClick);  
        </script>
        """

        for sensebox in sensebox_table:
            # print(sensebox.name)
            map_scripts += f"""
                <script>
                    var marker = L.marker([{sensebox.location_latitude}, {sensebox.location_longitude}], {'{icon: greyIcon}' if sensebox.error_message else '{icon: blueIcon}'}).addTo(map);
                
                    // Popup-Content als DOM-Element und nicht als String
                    marker.bindPopup(function() {{
                        var container = document.createElement('div');
                        container.innerHTML = `
                            <b>{sensebox.name}</b><br>
                            <button class='btn btn-primary mt-2' 
                                hx-get='draw_graph/{sensebox.sensebox_id}/' 
                                hx-target='#sensebox_graph' 
                                hx-swap='innerHTML'>
                                Zeige Daten
                            </button>
                            
                            <p style="color:red;">{sensebox.error_message if sensebox.error_message else ''}</p>
                            
                            <a class="mt-2" href="https://opensensemap.org/explore/{sensebox.sensebox_id}" target="_blank">Link zur Box</a>
                        `;
                        return container;
                    }});
                    
                   
                // Überprüfe auf das Popup-Öffnen und wende htmx.process() an
                marker.on('popupopen', function(e) {{
                    // Popup-Inhalt wurde in das DOM eingefügt, jetzt htmx verarbeiten
                    var popupContent =
                            e.popup.getElement(); // Popup - Element abrufen
                            htmx.process(popupContent); // htmx auf den Popup - Inhalt anwenden
                            console.log('htmx neu geladen');
                }});
                    
                </script>
            """

        # make target for the graph empty, to remove some errors
        map_scripts += """<script>
                    document.body.addEventListener('htmx:configRequest', function(evt) {
                        // Prüfen, ob das Event von einem Button mit der Klasse 'btn-primary' ausgelöst wurde
                        if (evt.detail.elt.classList.contains('btn-primary')) {
                            // Hole das Ziel-Element für den Button
                            var target = document.querySelector(evt.detail.elt.getAttribute('hx-target'));
                
                            // Leere das Ziel-Element und füge eine Ladeanimation ein
                            if (target) {
                                target.innerHTML = `
                                    <div class="d-flex flex-column justify-content-center align-items-center min-vh-100">
                                        <div class="spinner-border" role="status" style="width: 6rem; height: 6rem;">
                                            <span class="visually-hidden">Loading...</span>
                                        </div>
                                        <strong role="status" class="mt-3">Lade Daten von der Sensebox...</strong>
                                    </div>
                                    `;
                            }
                            sidebar.open('home');
                        }
                    });
                </script>"""

        # print(request.META.get('VIEWport'))

        context['map_scripts'] = map_scripts
        return context
