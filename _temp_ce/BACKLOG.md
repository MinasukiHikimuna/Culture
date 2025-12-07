# CultureExtractor Backlog

## Future Development Phases

### Phase 2: Frontend Pages & Components

- [ ] Core UI Components

  - Release card/grid component with lazy loading
  - Detailed release view with image gallery
  - Media viewer/player components
  - Search and filter interface
  - Navigation and layout components
  - Loading states and error boundaries

- [ ] Pages & Routing

  - Home/Dashboard page with stats (`/`)
  - Browse releases page with pagination (`/releases`)
  - Release detail page (`/releases/[id]`)
  - Search results page (`/search`)
  - Performers page (`/performers`)
  - Tags page (`/tags`)
  - Sites page (`/sites`)

- [ ] Advanced UI Features
  - Responsive design for mobile/tablet
  - Dark/light mode toggle
  - Infinite scroll or pagination
  - Advanced filtering and sorting
  - Bulk selection capabilities

### Phase 3: Media Handling & Performance

- [ ] Media Management

  - Static file serving for downloaded content
  - Image optimization with NextJS Image component
  - Video preview/thumbnail generation
  - Secure media access controls

- [ ] Performance Optimization
  - Database query optimization
  - Caching strategies (Redis for future)
  - Image optimization and lazy loading
  - Bundle optimization

### Phase 4: Advanced Features

- [ ] User Experience Enhancements

  - Real-time updates (Server-Sent Events or WebSockets)
  - Progressive Web App (PWA) capabilities
  - Offline support for browsing
  - Export functionality (JSON, CSV)

- [ ] Integration & Management
  - Bulk operations (mark as reviewed, delete, etc.)
  - Integration hooks for Stash app
  - Content curation tools
  - Statistics and analytics dashboard

### Phase 5: Deployment & Production

- [ ] Containerization

  - Docker setup for NextJS application
  - Update docker-compose.yml to include webapp service
  - Production environment configuration
  - Health checks and monitoring

- [ ] Documentation & Testing
  - API documentation
  - User guide for web interface
  - Basic testing setup with Jest/React Testing Library
  - End-to-end testing with Playwright

## Future Feature Ideas

### Authentication & User Management

- [ ] NextAuth.js integration
- [ ] User roles and permissions
- [ ] Session management
- [ ] API key authentication for external tools

### Advanced Search & Discovery

- [ ] Full-text search with PostgreSQL
- [ ] Elasticsearch integration for advanced search
- [ ] Recommendation engine
- [ ] Similar content suggestions
- [ ] Advanced filtering by metadata

### Content Management

- [ ] Content rating and review system
- [ ] Tagging and categorization tools
- [ ] Duplicate detection and merging
- [ ] Content moderation tools
- [ ] Batch operations interface

### Integrations

- [ ] Stash integration API
- [ ] Webhook support for external tools
- [ ] Import/export functionality
- [ ] Third-party scraper plugins
- [ ] Metadata enhancement services

### Performance & Scalability

- [ ] Redis caching layer
- [ ] CDN integration for media files
- [ ] Database indexing optimization
- [ ] Background job processing
- [ ] Media compression and optimization

### Mobile & Accessibility

- [ ] Progressive Web App (PWA)
- [ ] Mobile app with React Native
- [ ] Accessibility compliance (WCAG)
- [ ] Keyboard navigation
- [ ] Screen reader support

### Analytics & Monitoring

- [ ] Usage analytics dashboard
- [ ] Performance monitoring
- [ ] Error tracking and logging
- [ ] System health checks
- [ ] Storage usage tracking

## Questions for Future Discussion

1. **Media Storage Strategy**: Local storage vs cloud storage vs hybrid approach
2. **Scalability**: Multi-instance deployment and load balancing
3. **Backup Strategy**: Automated backups for both database and media files
4. **Content Distribution**: CDN setup for media file delivery
5. **Mobile Strategy**: PWA vs native mobile app
6. **Search Performance**: When to consider Elasticsearch vs PostgreSQL full-text search
