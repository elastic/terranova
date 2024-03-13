<!--
Copyright (c) 2024 Elastic.

This file is part of terranova.
See https://github.com/elastic/terranova for further info.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->
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
### {{ resource.name }} - {{ resource.type }}
{% endif %}

{% for key, values in resource.attrs.items() -%}
{% if key != 'name' -%}
{% for value in values -%}
* {{ key }}: {{ value }}
{% endfor %}
{%- endif %}
{%- endfor %}
{% endfor %}
