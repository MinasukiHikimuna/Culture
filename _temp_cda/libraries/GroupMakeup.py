class GroupMakeup:
    """Class to handle group makeup tag management and validation"""
    
    # Gender mapping for performer types
    GENDER_MAP = {
        'MALE': 'B',
        'FEMALE': 'G',
        'TRANSGENDER_FEMALE': 'T',
        'TRANSGENDER_MALE': 'T',
        'NON_BINARY': 'N'
    }
    
    # Map common counts to their base names
    COUNT_MAP = {
        1: 'Solo',
        2: 'Twosome',
        3: 'Threesome',
        4: 'Foursome',
        5: 'Fivesome',
        6: 'Sixsome',
        7: 'Sevensome'
    }
    
    # Tags that should cause a scene to be excluded from validation
    EXCLUDE_TAG_NAMES = [
        'Multiple Sex Scenes in a Scene',
        'Full Movie',
        'Behind the Scenes',
        'Missing Performer (Male)',
        'Non-Sex Performer'
    ]
    
    def __init__(self, tags):
        """Initialize with list of available tags"""
        self.tags = {tag['name']: tag['id'] for tag in tags}
        self.exclude_tag_ids = {tag['id'] for tag in tags if tag['name'] in self.EXCLUDE_TAG_NAMES}
    
    def get_performer_makeup(self, performers):
        """Convert performers list to a makeup string like 'BGT' (sorted alphabetically)"""
        return ''.join(sorted(self.GENDER_MAP[p['gender']] for p in performers))
    
    def get_expected_group_tags(self, performers):
        """Get the expected group makeup tags based on performer count and genders"""
        makeup = self.get_performer_makeup(performers)
        count = len(performers)
        
        if count not in self.COUNT_MAP:
            return []
            
        base_tag = self.COUNT_MAP[count]
        tag_names = [base_tag]  # Always include base tag
        
        # Add specific makeup tag if applicable
        if count == 1:
            if makeup == 'B':
                tag_names.append(f'{base_tag} Male')
            elif makeup == 'G':
                tag_names.append(f'{base_tag} Female')
            elif makeup == 'T':
                tag_names.append(f'{base_tag} Trans')
        else:
            # Add orientation-based tags
            if all(p['gender'] == 'MALE' for p in performers):
                tag_names.append(f'{base_tag} (Gay)')
            elif all(p['gender'] == 'FEMALE' for p in performers):
                tag_names.append(f'{base_tag} (Lesbian)')
            elif all(p['gender'] in ['TRANSGENDER_FEMALE', 'TRANSGENDER_MALE'] for p in performers):
                tag_names.append(f'{base_tag} (Trans)')
            elif len(performers) == 2:
                # Special case for twosomes
                if makeup == 'BG':
                    tag_names.append(f'{base_tag} (Straight)')
                elif 'GT' in makeup or 'BT' in makeup:
                    tag_names.append(f'{base_tag} (Trans)')
            
            # Add specific makeup tag for mixed groups of 3+ performers
            if count > 2 and not all(p['gender'] == 'FEMALE' for p in performers):
                tag_names.append(f'{base_tag} ({makeup})')
        
        # Convert tag names to structs with id and name
        return [{'id': self.tags[name], 'name': name} 
                for name in tag_names if name in self.tags]
    
    def get_scene_group_makeup_issues(self, scene):
        """Get group makeup issues for a scene and return as a dict"""
        
        # Skip scenes with exclude tags
        if any(tag['id'] in self.exclude_tag_ids for tag in scene['tags']):
            return None
        
        scene_tags = {tag['name']: tag['id'] for tag in scene['tags']}
        group_makeup_tags = {tag['name']: tag['id'] 
                            for tag in scene['tags'] 
                            if any(tag['name'].startswith(prefix) 
                                for prefix in self.COUNT_MAP.values())}
        
        expected_tags = self.get_expected_group_tags(scene['performers'])
        expected_tag_dict = {tag['name']: tag['id'] for tag in expected_tags}
        
        issues = []
        
        # Check for missing expected tags
        missing_tags = [{'id': tag['id'], 'name': tag['name']} 
                       for tag in expected_tags if tag['name'] not in scene_tags]
        if missing_tags:
            issues.append(f"Missing tags: {', '.join(tag['name'] for tag in missing_tags)}")
            
        # Check for conflicting or incomplete tag sets
        for prefix in self.COUNT_MAP.values():
            matching_tags = [(name, id) for name, id in group_makeup_tags.items() if name.startswith(prefix)]
            if matching_tags:
                # Must have base tag if any specific tags exist
                if prefix not in scene_tags:
                    issues.append(f"Missing base {prefix} tag but has specific tags: {', '.join(name for name, _ in matching_tags)}")
                
                # Check for incorrect specific tags
                if any(tag['name'].startswith(prefix) for tag in expected_tags):
                    unexpected_tags = [{'id': id, 'name': name} 
                                     for name, id in matching_tags 
                                     if name not in expected_tag_dict]
                    if unexpected_tags:
                        issues.append(f"Has incorrect specific tags: {', '.join(tag['name'] for tag in unexpected_tags)}")
        
        if not issues:
            return None
            
        # Format performers as string
        performers_str = "; ".join(f"{p['name']} ({p['gender']})" for p in scene['performers'])
        
        return {
            'scene_id': int(scene['id']),
            'title': scene['title'],
            'performers': performers_str,
            'expected_tags': [{'id': tag['id'], 'name': tag['name']} for tag in expected_tags],
            'actual_group_tags': [{'id': id, 'name': name} for name, id in group_makeup_tags.items()],
            'issues': "; ".join(issues)
        }