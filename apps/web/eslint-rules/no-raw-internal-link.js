// PRD §4: every internal link goes through the locale-aware Link, so no link can drop the locale.
// Bans <a href="/..."> in JSX and next/link imports outside components/Link.tsx. The admin is English-only, not localized.
module.exports = {
  meta: {
    type: "problem",
    docs: { description: "Use the locale-aware Link for internal links" },
    messages: {
      rawAnchor: 'Internal link "{{href}}" must use the locale-aware <Link> from "@/components/Link".',
      nextLink: 'Import Link from "@/components/Link" instead of "next/link" (it keeps the locale).',
    },
    schema: [],
  },
  create(context) {
    const file = context.filename || context.getFilename();
    const isLinkModule = /components[\\/]Link\.tsx$/.test(file);
    const isAdmin = /[\\/]app[\\/]admin[\\/]|components[\\/]admin[\\/]/.test(file);
    return {
      ImportDeclaration(node) {
        if (node.source.value === "next/link" && !isLinkModule && !isAdmin) {
          context.report({ node, messageId: "nextLink" });
        }
      },
      JSXOpeningElement(node) {
        if (node.name.type !== "JSXIdentifier" || node.name.name !== "a") return;
        const href = node.attributes.find((a) => a.type === "JSXAttribute" && a.name && a.name.name === "href");
        if (!href || !href.value) return;
        let value = null;
        if (href.value.type === "Literal") value = href.value.value;
        else if (href.value.type === "JSXExpressionContainer" && href.value.expression.type === "Literal")
          value = href.value.expression.value;
        else if (href.value.type === "JSXExpressionContainer" && href.value.expression.type === "TemplateLiteral")
          value = href.value.expression.quasis[0].value.cooked;
        if (typeof value === "string" && value.startsWith("/") && !value.startsWith("//") && !isLinkModule && !isAdmin
            && !value.startsWith("/api/") && !value.startsWith("/media/")) {
          context.report({ node, messageId: "rawAnchor", data: { href: value } });
        }
      },
    };
  },
};
