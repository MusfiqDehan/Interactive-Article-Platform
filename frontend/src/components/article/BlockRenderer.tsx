"use client";

import { EditorBlock } from "@/lib/types";
import ParagraphBlock from "./ParagraphBlock";
import HeaderBlock from "./HeaderBlock";
import ImageBlock from "./ImageBlock";
import VideoBlock from "./VideoBlock";
import AudioBlock from "./AudioBlock";
import YouTubeBlock from "./YouTubeBlock";
import QuoteBlock from "./QuoteBlock";
import ListBlock from "./ListBlock";
import DelimiterBlock from "./DelimiterBlock";
import CodeBlock from "./CodeBlock";
import InteractiveTextBlock from "./InteractiveTextBlock";
import InteractiveImageBlock from "./InteractiveImageBlock";
import InteractiveAudioBlock from "./InteractiveAudioBlock";
import InteractiveVideoBlock from "./InteractiveVideoBlock";
import InteractiveYouTubeBlock from "./InteractiveYouTubeBlock";

interface BlockRendererProps {
  blocks: EditorBlock[];
}

const blockComponents: Record<string, React.ComponentType<{ data: Record<string, unknown> }>> = {
  paragraph: ParagraphBlock,
  header: HeaderBlock,
  image: ImageBlock,
  video: VideoBlock,
  audio: AudioBlock,
  youtube: YouTubeBlock,
  embed: YouTubeBlock,
  quote: QuoteBlock,
  list: ListBlock,
  delimiter: DelimiterBlock,
  code: CodeBlock,
  interactive_text: InteractiveTextBlock,
  interactive_image: InteractiveImageBlock,
  interactive_audio: InteractiveAudioBlock,
  interactive_video: InteractiveVideoBlock,
  interactive_youtube: InteractiveYouTubeBlock,
};

export default function BlockRenderer({ blocks }: BlockRendererProps) {
  if (!blocks || blocks.length === 0) {
    return (
      <div className="text-center py-12 text-slate-400 dark:text-slate-500">
        No content available.
      </div>
    );
  }

  return (
    <div className="prose prose-slate dark:prose-invert max-w-none prose-lg prose-headings:font-display prose-a:text-primary-600 dark:prose-a:text-primary-400 prose-img:rounded-xl">
      {blocks.map((block, index) => {
        const Component = blockComponents[block.type];
        if (!Component) {
          return null;
        }
        return (
          <div key={block.id || index} className="mb-6">
            <Component data={block.data} />
          </div>
        );
      })}
    </div>
  );
}
