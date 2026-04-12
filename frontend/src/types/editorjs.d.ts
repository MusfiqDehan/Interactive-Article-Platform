declare module "@editorjs/embed" {
  import { BlockToolConstructable } from "@editorjs/editorjs";
  const Embed: BlockToolConstructable;
  export default Embed;
}

declare module "@editorjs/header" {
  import { BlockToolConstructable } from "@editorjs/editorjs";
  const Header: BlockToolConstructable;
  export default Header;
}

declare module "@editorjs/list" {
  import { BlockToolConstructable } from "@editorjs/editorjs";
  const List: BlockToolConstructable;
  export default List;
}

declare module "@editorjs/quote" {
  import { BlockToolConstructable } from "@editorjs/editorjs";
  const Quote: BlockToolConstructable;
  export default Quote;
}

declare module "@editorjs/delimiter" {
  import { BlockToolConstructable } from "@editorjs/editorjs";
  const Delimiter: BlockToolConstructable;
  export default Delimiter;
}

declare module "@editorjs/image" {
  import { BlockToolConstructable } from "@editorjs/editorjs";
  const ImageTool: BlockToolConstructable;
  export default ImageTool;
}

declare module "@editorjs/code" {
  import { BlockToolConstructable } from "@editorjs/editorjs";
  const CodeTool: BlockToolConstructable;
  export default CodeTool;
}

declare module "@editorjs/inline-code" {
  import { InlineToolConstructable } from "@editorjs/editorjs";
  const InlineCode: InlineToolConstructable;
  export default InlineCode;
}

declare module "@editorjs/marker" {
  import { InlineToolConstructable } from "@editorjs/editorjs";
  const Marker: InlineToolConstructable;
  export default Marker;
}
