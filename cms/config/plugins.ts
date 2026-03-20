import _ from "lodash";

/**
 * Workaround for a bug in @strapi/plugin-documentation: 
 * https://github.com/strapi/strapi/issues/22808 where the schema
 * generator uses a shared `typeMap` to prevent circular references. Any
 * relation target already expanded elsewhere in the recursive tree is
 * reduced to just `{ id, documentId }`. This post-processes the generated
 * OpenAPI spec and restores full properties for those truncated relations.
 */

interface SchemaProperty {
  type?: string;
  properties?: Record<string, SchemaProperty>;
  items?: SchemaProperty | { $ref: string };
  $ref?: string;
  [key: string]: unknown;
}

interface Schema {
  type?: string;
  properties?: Record<string, SchemaProperty>;
  required?: string[];
  [key: string]: unknown;
}

interface ContentTypeAttribute {
  type: string;
  relation?: string;
  target?: string;
  [key: string]: unknown;
}

interface ContentType {
  attributes: Record<string, ContentTypeAttribute>;
  [key: string]: unknown;
}

const isTruncatedRelation = (prop: SchemaProperty): boolean =>
  prop != null &&
  prop.type === "object" &&
  prop.properties != null &&
  Object.keys(prop.properties).length === 2 &&
  prop.properties.id != null &&
  prop.properties.documentId != null;

const pascalCase = (string: string): string =>
  _.upperFirst(_.camelCase(string));

const patchTruncatedRelations = (schemas: Record<string, Schema>): void => {
  // Build a map from content type UID to its top-level schema name
  const uidToSchemaName: Record<string, string> = {};
  const apiContentTypes: [string, ContentType][] = Object.entries(
    strapi.contentTypes
  ).filter(([uid]) => uid.startsWith("api::"));

  for (const [uid] of apiContentTypes) {
    const apiName = uid.split("::")[1]?.split(".")[0];
    const ctName = uid.split(".")[1];
    const uniqueName =
      apiName === ctName
        ? _.upperFirst(apiName)
        : `${_.upperFirst(apiName)} - ${_.upperFirst(ctName)}`;
    const schemaName = pascalCase(uniqueName);
    uidToSchemaName[uid] = schemaName;
  }

  // For each top-level schema, check its properties for truncated relations
  // and restore them from the content type's relation target
  for (const [schemaName, schema] of Object.entries(schemas)) {
    if (!schema.properties) continue;

    // Find the content type UID for this schema
    const ctEntry = apiContentTypes.find(
      ([uid]) => uidToSchemaName[uid] === schemaName
    );
    if (!ctEntry) continue;

    const ct = ctEntry[1];

    for (const [propName, propSchema] of Object.entries(schema.properties)) {
      const attribute = ct.attributes[propName];
      if (!attribute || attribute.type !== "relation" || !attribute.target)
        continue;

      const targetSchemaName = uidToSchemaName[attribute.target];
      if (!targetSchemaName || !schemas[targetSchemaName]) continue;

      const isToMany = attribute.relation?.includes("ToMany");

      if (isToMany) {
        // Array relation — check items
        const arrayProp = propSchema as SchemaProperty;
        if (
          arrayProp.type === "array" &&
          arrayProp.items &&
          !("$ref" in arrayProp.items) &&
          isTruncatedRelation(arrayProp.items)
        ) {
          arrayProp.items = {
            $ref: `#/components/schemas/${targetSchemaName}`,
          };
        }
      } else {
        // Single relation — check object directly
        if (isTruncatedRelation(propSchema)) {
          schema.properties[propName] = {
            $ref: `#/components/schemas/${targetSchemaName}`,
          };
        }
      }
    }
  }
};

interface DocumentationDraft {
  components?: { schemas?: Record<string, Schema> };
  paths: Record<
    string,
    {
      get?: {
        parameters: Array<{ name: string; [key: string]: unknown }>;
      };
      [key: string]: unknown;
    }
  >;
}

export default {
  documentation: {
    config: {
      "x-strapi-config": {
        mutateDocumentation: (generatedDocumentationDraft: DocumentationDraft) => {
          // Fix truncated relation schemas
          if (generatedDocumentationDraft.components?.schemas) {
            patchTruncatedRelations(generatedDocumentationDraft.components.schemas);
          }

          Object.keys(generatedDocumentationDraft.paths).forEach((path) => {
            // check if it has {id} in the path
            if (path.includes("{id}")) {
              // add `populate` as params
              if (generatedDocumentationDraft.paths[path].get) {
                if (!generatedDocumentationDraft.paths[path].get.parameters.find((param: { name: string }) => param.name === "populate")) {
                  generatedDocumentationDraft.paths[path].get.parameters.push(
                    {
                      "name": "populate",
                      "in": "query",
                      "description": "Relations to return",
                      "deprecated": false,
                      "required": false,
                      "schema": {
                        "type": "string"
                      }
                    },
                  );
                }
              }
            }
          });
        },
      },
    },
  },
  'config-sync': {
    enabled: true,
    config: {
      syncDir: "config/sync/",
      // minify: false,
      // soft: false,
      // importOnBootstrap: false,
      // customTypes: [],
      // excludedTypes: [],
      excludedConfig: [
        "core-store.plugin_users-permissions_grant",
        "core-store.plugin_upload_metrics",
        "core-store.strapi_content_types_schema",
        "core-store.ee_information",
        "core-store.plugin_localazy_identity"
      ],
    },
  },
};
