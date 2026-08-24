```{=html}
<%
const letters = [...new Set(items.map(item => item.title[0].toUpperCase()))].sort();
%>


<% for (const letter of letters) { %>
  <h2 id="<%= letter %>"><%= letter %></h2>
  <dl>
  <% const letterItems = items.filter(item => item.title[0].toUpperCase() === letter); %>
  <% for (const item of letterItems) { %>
    <dt><a href="<%= item.path %>"><%= item.title %></a></dt>
    <dd><%= item.description %></dd>
  <% } %>
  </dl>
<% } %>
```
