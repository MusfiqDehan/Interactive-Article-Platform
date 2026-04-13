// ============ Auth Types ============
export interface User {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  role: "admin" | "author" | "reader";
  bio: string;
  avatar: string | null;
  date_joined: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  username: string;
  password: string;
  password_confirm: string;
  first_name?: string;
  last_name?: string;
}

// ============ Category Types ============
export interface SubCategory {
  id: number;
  category: number;
  name: string;
  slug: string;
  description: string;
  is_active: boolean;
  order: number;
  created_at: string;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  description: string;
  image: string | null;
  is_active: boolean;
  order: number;
  subcategories: SubCategory[];
  article_count: number;
  created_at: string;
  updated_at: string;
}

// ============ Article Types ============
export interface Author {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  avatar: string | null;
}

export interface Article {
  id: number;
  title: string;
  slug: string;
  author: Author;
  category: Category | null;
  subcategory: SubCategory | null;
  content: EditorJSContent;
  excerpt: string;
  featured_image: string;
  status: "draft" | "published" | "archived";
  is_featured: boolean;
  reading_time: number;
  views_count: number;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ArticleListItem {
  id: number;
  title: string;
  slug: string;
  author: Author;
  category: Category | null;
  excerpt: string;
  featured_image: string;
  status: "draft" | "published" | "archived";
  is_featured: boolean;
  reading_time: number;
  views_count: number;
  published_at: string | null;
  created_at: string;
}

// ============ Editor.js Types ============
export interface EditorJSContent {
  time?: number;
  blocks: EditorBlock[];
  version?: string;
}

export interface EditorBlock {
  id?: string;
  type: string;
  data: Record<string, unknown>;
}

export interface InteractiveAnnotation {
  id: string;
  type: "text" | "image" | "audio" | "video" | "youtube";
  modal_title: string;
  // type === "text"
  modal_content?: string;
  // type === "image"
  image_url?: string;
  image_caption?: string;
  // type === "audio"
  audio_url?: string;
  // type === "video"
  video_url?: string;
  // type === "youtube"
  youtube_source?: string;
}

export interface ImageHotspot {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  shape: "circle" | "rect";
  modal_title: string;
  modal_content: string;
}

export interface MediaChapter {
  id: string;
  time: number; // seconds from start
  label: string;
  modal_title: string;
  modal_content: string;
}

// ============ Media Types ============
export interface MediaFile {
  id: number;
  file: string;
  url: string;
  file_type: "image" | "audio" | "video" | "document";
  title: string;
  alt_text: string;
  file_size: number;
  mime_type: string;
  uploaded_by: number;
  created_at: string;
}

// ============ API Types ============
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface StatsResponse {
  total_articles: number;
  published_articles: number;
  draft_articles: number;
  total_views: number;
  total_categories: number;
  total_users: number | null;
}
