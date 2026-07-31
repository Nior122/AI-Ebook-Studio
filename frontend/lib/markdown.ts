// Minimal markdown <-> HTML conversion for the rich text editor.
// Chapters are stored as markdown; the editor renders contentEditable HTML and
// converts back on input. Deliberately small and dependency-free.

const ESCAPE: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
};

export function escapeHtml(text: string): string {
  return text.replace(/[&<>]/g, (ch) => ESCAPE[ch] ?? ch);
}

function inline(text: string): string {
  return text
    .replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g, (_m, alt: string, src: string) => {
      return `<img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}" class="rounded-md border border-border max-w-full" />`;
    })
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_m, label: string, href: string) => {
      return `<a href="${escapeHtml(href)}" target="_blank" rel="noreferrer" class="text-primary underline">${inline(label)}</a>`;
    })
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

/** Convert markdown chapter content to HTML for the contentEditable editor. */
export function mdToHtml(markdown: string): string {
  const lines = markdown.split("\n");
  const html: string[] = [];
  let list: string[] | null = null;

  const flushList = () => {
    if (list) {
      html.push(`<ul>${list.join("")}</ul>`);
      list = null;
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flushList();
      continue;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushList();
      const level = heading[1].length;
      html.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      continue;
    }
    const bullet = line.match(/^\s*[-*•]\s+(.+)$/);
    if (bullet) {
      list = list ?? [];
      list.push(`<li>${inline(bullet[1])}</li>`);
      continue;
    }
    const quote = line.match(/^>\s?(.+)$/);
    if (quote) {
      flushList();
      html.push(`<blockquote class="border-l-2 border-border pl-3 text-muted-foreground">${inline(quote[1])}</blockquote>`);
      continue;
    }
    const rule = line.match(/^---+$/);
    if (rule) {
      flushList();
      html.push("<hr class=\"my-3 border-border\" />");
      continue;
    }
    flushList();
    html.push(`<p>${inline(line)}</p>`);
  }
  flushList();
  return html.join("\n");
}

function nodeToMd(node: Node, depth: number): string {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.textContent ?? "";
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return "";
  const el = node as HTMLElement;
  const tag = el.tagName.toLowerCase();
  const children = Array.from(el.childNodes).map((child) => nodeToMd(child, depth + 1)).join("");

  switch (tag) {
    case "p":
      return `${children}\n\n`;
    case "br":
      return "\n";
    case "h1":
    case "h2":
    case "h3":
      return `\n${"#".repeat(Number(tag[1]))} ${children.trim()}\n\n`;
    case "ul":
      return Array.from(el.children)
        .map((li) => `- ${nodeToMd(li, depth + 1).trim()}`)
        .join("\n") + "\n\n";
    case "ol":
      return Array.from(el.children)
        .map((li, index) => `${index + 1}. ${nodeToMd(li, depth + 1).trim()}`)
        .join("\n") + "\n\n";
    case "li":
      return children.trim();
    case "blockquote":
      return children
        .trim()
        .split("\n")
        .map((part) => `> ${part}`)
        .join("\n") + "\n\n";
    case "strong":
    case "b":
      return `**${children}**`;
    case "em":
    case "i":
      return `*${children}*`;
    case "code":
      return `\`${children}\``;
    case "a": {
      const href = el.getAttribute("href") ?? "";
      return href ? `[${children}](${href})` : children;
    }
    case "img": {
      const src = el.getAttribute("src") ?? "";
      const alt = el.getAttribute("alt") ?? "";
      return src ? `![${alt}](${src})` : "";
    }
    case "hr":
      return `\n---\n\n`;
    default:
      return children;
  }
}

/** Convert editor HTML back to markdown. */
export function htmlToMd(html: string): string {
  if (typeof document === "undefined") return html;
  const container = document.createElement("div");
  container.innerHTML = html;
  const markdown = Array.from(container.childNodes).map((child) => nodeToMd(child, 0)).join("");
  return markdown.replace(/\n{3,}/g, "\n\n").trim() + "\n";
}
