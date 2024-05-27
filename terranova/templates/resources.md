# {{ manifest.metadata.name }}

*{{ manifest.metadata.description }}*

{% if manifest.metadata.url is not none -%}
* [Source]({{ manifest.metadata.url }})
{%- endif %}
{% if manifest.metadata.contact is not none -%}
* [Contact]({{ manifest.metadata.contact }})
{%- endif %}

## Resources

{% for resource in resources -%}

{% if resource.attrs.name | length > 0 %}
### {{ resource.attrs.name | first }}
{% else %}
### {{ resource.block_type }} - {{ resource.name }} - {{ resource.type }}
{% endif %}

{% for key, values in resource.attrs.items() -%}
{% if key != 'name' -%}
{% for value in values -%}
* {{ key }}: {{ value }}
{% endfor %}
{%- endif %}
{%- endfor %}
{% endfor %}
